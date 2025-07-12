# handlers.py
import time
import json
import os
import datetime
import msgpack
from threading import Thread, Event, Lock
from Adafruit_IO import Client

# Import hardware-specific libraries
import board
import busio
from digitalio import DigitalInOut
import adafruit_rfm9x

from database import DatabaseManager

class BaseHandler(Thread):
    def __init__(self, config, db_manager):
        super().__init__(daemon=True)
        self.db = db_manager
        self._stop_event = Event()
        self.name = self.__class__.__name__
        self.interval = 300
        self.update_config(config)

    def run(self):
        print(f"[{self.name}] Service started.")
        self.loop()
        print(f"[{self.name}] Service stopped.")

    def stop(self):
        self._stop_event.set()
        if hasattr(self, 'close'):
            self.close()
        self.join()

    def update_config(self, new_config):
        self.config = new_config
        self.update_interval()
        print(f"[{self.name}] Configuration updated.")

    def update_interval(self):
        raise NotImplementedError

    def loop(self):
        raise NotImplementedError

class AdafruitIOHandler(BaseHandler):
    def __init__(self, config, db_manager, aio_client, aio_prefix):
        self.aio_client = aio_client
        self.aio_prefix = aio_prefix
        self.last_sent_ids = {}
        self._feed_key_cache = {}
        super().__init__(config, db_manager)

    def update_interval(self):
        self.interval = self.config.get('timing', {}).get('adafruit_io_interval_seconds', 300)
        self._feed_key_cache = {}

    def _get_feed_key(self, sensor_name, metric_name):
        cache_key = f"{sensor_name}.{metric_name}"
        if cache_key in self._feed_key_cache:
            return self._feed_key_cache[cache_key]
        if sensor_name == self.config.get('rain_gauge', {}).get('name'):
            key = self.config['rain_gauge'].get('feed_key')
            if key: self._feed_key_cache[cache_key] = key; return key
        for sensor_config in self.config.get('sensors', {}).values():
            if sensor_config.get('name') == sensor_name:
                metric_config = sensor_config.get('metrics', {}).get(metric_name)
                if metric_config and 'feed_key' in metric_config:
                    key = metric_config['feed_key']; self._feed_key_cache[cache_key] = key; return key
        fallback_key = f"{sensor_name}-{metric_name}"; self._feed_key_cache[cache_key] = fallback_key; return fallback_key

    def loop(self):
        while not self._stop_event.wait(self.interval):
            if not self.config.get('services', {}).get('adafruit_io_enabled', False): continue
            print(f"[{self.name}] Checking for new data to upload...")
            latest_readings_by_station = self.db.get_latest_readings_by_station()
            for station_id, readings in latest_readings_by_station.items():
                for key, data in readings.items():
                    if self.last_sent_ids.get(key) != data['id']:
                        try:
                            feed_key = self._get_feed_key(data['sensor'], data['metric'])
                            if not feed_key: continue
                            full_feed_id = f"{self.aio_prefix}.station-{station_id}.{feed_key}"
                            print(f"[{self.name}] Sending {data['value']:.2f} to {full_feed_id}")
                            self.aio_client.send_data(full_feed_id, data['value'])
                            self.last_sent_ids[key] = data['id']
                        except Exception as e:
                            print(f"[{self.name}] ERROR sending data for {key}: {e}")


class LoRaHandler(BaseHandler):
    def __init__(self, config, db_manager):
        self.last_data_sent_id = 0
        self.rfm9x = None
        self.lora_lock = Lock()
        self.db_connections = {'local': db_manager}
        super().__init__(config, db_manager)
        
        self.init_lora_hardware()

        if self.rfm9x:
            print(f"[{self.name}] Initialized in '{self.role}' role.")
            self.receive_thread = Thread(target=self.receive_loop, daemon=True)
            self.receive_thread.start()
            if self.role == 'remote':
                self.send_thread = Thread(target=self.send_loop, daemon=True)
                self.send_thread.start()
        else:
            print(f"[{self.name}] LoRa hardware not found. Handler will be inactive.")

    def init_lora_hardware(self):
        try:
            CS = DigitalInOut(board.CE1)
            RESET = DigitalInOut(board.D25)
            spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)
            self.rfm9x = adafruit_rfm9x.RFM9x(spi, CS, RESET, self.lora_config.get('frequency', 915.0))
            self.rfm9x.tx_power = self.lora_config.get('tx_power', 23)
            print(f"[{self.name}] RFM9x LoRa radio initialized in BROADCAST mode.")
        except (ValueError, RuntimeError) as e:
            print(f"[{self.name}] ERROR: RFM9x radio not found or failed to initialize: {e}")
            self.rfm9x = None

    def get_remote_db(self, station_name):
        if station_name in self.db_connections:
            return self.db_connections[station_name]
        
        print(f"[{self.name}] Creating new database connection for remote station: {station_name}")
        main_db_path = self.db_connections['local'].db_path
        base_dir = os.path.dirname(main_db_path)
        remote_db_path = os.path.join(base_dir, f"{station_name}.db")
        
        db_manager = DatabaseManager(remote_db_path)
        self.db_connections[station_name] = db_manager
        return db_manager

    def close(self):
        print(f"[{self.name}] Closing all database connections.")
        for name, db_conn in self.db_connections.items():
            if name != 'local':
                db_conn.close()

    def update_interval(self):
        self.interval = self.config.get('timing', {}).get('transmission_interval_seconds', 60)
        self.lora_config = self.config.get('lora', {})
        self.role = self.lora_config.get('role')

    def loop(self):
        while not self._stop_event.is_set():
            time.sleep(1)

    def send_loop(self):
        if not self.rfm9x: return
        print(f"[{self.name}] Starting send loop.")
        while not self._stop_event.wait(self.interval):
            if not self.config.get('services', {}).get('lora_enabled', False): continue
            
            if self.role == 'remote':
                self.send_data_payload()

    def send_data_payload(self):
        records = self.db.get_unsent_lora_data(self.config['station_info']['station_id'], self.last_data_sent_id)
        if not records: return
        
        # --- OPTIMIZATION: Remove redundant station_id from each record ---
        payload_records = []
        for r in records:
            record_dict = dict(r)
            del record_dict['station_id'] # Remove the key
            payload_records.append(record_dict)

        packet = {
            'type': 'data',
            'station_name': self.config.get('station_info', {}).get('station_name', 'unknown'),
            'station_id': self.config.get('station_info', {}).get('station_id', 0),
            'payload': payload_records # Use the optimized list
        }

        print(f"[{self.name}] Broadcasting {len(records)} data records.")
        with self.lora_lock:
            packed_data = msgpack.packb(packet)
            self.rfm9x.send(packed_data)
        self.last_data_sent_id = records[-1]['id']

    def receive_loop(self):
        if not self.rfm9x: return
        print(f"[{self.name}] Starting receive loop.")
        while not self._stop_event.is_set():
            if not self.config.get('services', {}).get('lora_enabled', False):
                time.sleep(5)
                continue
            
            with self.lora_lock:
                packet = self.rfm9x.receive(timeout=5.0)
            
            if not packet: continue

            rssi = self.rfm9x.last_rssi
            try:
                data = msgpack.unpackb(packet)
                packet_type = data.get('type')
                
                if self.role == 'base' and packet_type == 'data':
                    self.handle_data_packet(data, rssi)

            except (msgpack.exceptions.UnpackException, AttributeError):
                print(f"[{self.name}] ERROR: Malformed LoRa packet received.")
            except Exception as e:
                print(f"[{self.name}] ERROR in receive_loop: {e}")

    def handle_data_packet(self, data, rssi):
        station_name = data.get('station_name', 'unknown_station')
        station_id = data.get('station_id') # Get the single ID from the header
        payload = data.get('payload', [])
        
        if not payload or not station_id:
            print(f"[{self.name}] Received data packet with no payload or station_id.")
            return

        print(f"[{self.name}] Received {len(payload)} data records from '{station_name}' (ID: {station_id}) with RSSI: {rssi}")
        
        remote_db = self.get_remote_db(station_name)
        
        for record in payload:
            # --- OPTIMIZATION: Use the station_id from the header for all records ---
            remote_db.write_reading(
                station_id=station_id, # Use the main ID here
                sensor=record['sensor'],
                metric=record['metric'],
                value=record['value'],
                rssi=rssi,
                timestamp=record['timestamp'] # Pass timestamp along
            )