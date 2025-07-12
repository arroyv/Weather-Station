# handlers.py
import time
import json
import os
import datetime
from threading import Thread, Event, Lock
from Adafruit_IO import Client

# Import hardware-specific libraries
import board
import busio
from digitalio import DigitalInOut
import adafruit_rfm9x

from database import DatabaseManager # Import DatabaseManager

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
            # Note: This sends data from ALL stations received by a base station
            latest_readings_by_station = self.db.get_latest_readings_by_station()
            for station_id, readings in latest_readings_by_station.items():
                for key, data in readings.items():
                    if self.last_sent_ids.get(key) != data['id']:
                        try:
                            feed_key = self._get_feed_key(data['sensor'], data['metric'])
                            if not feed_key: continue
                            # Add station ID to feed key for uniqueness
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
        # This will hold connections to remote DBs
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
            self.rfm9x.enable_crc = True
            self.rfm9x.ack_retries = self.lora_config.get('ack_retries', 3)
            self.rfm9x.ack_timeout = self.lora_config.get('ack_timeout', 0.1)
            self.rfm9x.tx_power = self.lora_config.get('tx_power', 23)
            # Addressing is removed for broadcast mode
            # print(f"[{self.name}] RFM9x LoRa radio initialized in BROADCAST mode.")

            self.rfm9x.node = 0 if self.role == 'base' else 1
            self.rfm9x.destination = 1 if self.role == 'base' else 0
            print(f"[{self.name}] RFM9x LoRa radio initialized. Freq: {self.rfm9x.frequency_mhz}, Power: {self.rfm9x.tx_power}")
        except (ValueError, RuntimeError) as e:
            print(f"[{self.name}] ERROR: RFM9x radio not found or failed to initialize: {e}")
            self.rfm9x = None

    def get_remote_db(self, station_name):
        """Gets or creates a DatabaseManager for a remote station."""
        if station_name in self.db_connections:
            return self.db_connections[station_name]

        print(f"[{self.name}] Creating new database connection for remote station: {station_name}")
        # Construct the path based on the main DB's directory
        main_db_path = self.db_connections['local'].db_path
        base_dir = os.path.dirname(main_db_path)
        remote_db_path = os.path.join(base_dir, f"{station_name}.db")

        db_manager = DatabaseManager(remote_db_path)
        self.db_connections[station_name] = db_manager
        return db_manager

    def close(self):
        """Close all database connections."""
        print(f"[{self.name}] Closing all database connections.")
        for name, db_conn in self.db_connections.items():
            if name != 'local': # The main one is closed by the main script
                db_conn.close()

    def update_interval(self):
        self.interval = self.config.get('timing', {}).get('transmission_interval_seconds', 60)
        self.time_sync_interval = self.config.get('timing', {}).get('lora_time_sync_interval_seconds', 3600)
        self.lora_config = self.config.get('lora', {})
        self.role = self.lora_config.get('role')

    def loop(self):
        """Main loop is now just waiting, as tasks are in threads."""
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
        # Use the local DB for sending this station's own data
        records = self.db.get_unsent_lora_data(self.config['station_info']['station_id'], self.last_data_sent_id)
        if not records: return

        packet = {
            'type': 'data',
            'station_name': self.config.get('station_info', {}).get('station_name', 'unknown'),
            'station_id': self.config.get('station_info', {}).get('station_id', 0),
            'payload': [dict(r) for r in records]
        }

        print(f"[{self.name}] Broadcasting {len(records)} data records.")
        # with self.lora_lock:
        #     for record in records:
        #         self.rfm9x.send(json.dumps(record).encode("utf-8"))
        # self.last_data_sent_id = records[-1]['id']
        with self.lora_lock:
            for record in records:
                message = json.dumps(dict(record)).encode("utf-8")
                success = self.rfm9x.send_with_ack(message)
                if success:
                    self.last_data_sent_id = record['id']
                else:
                    break

    def receive_loop(self):
        if not self.rfm9x: return
        print(f"[{self.name}] Starting receive loop.")
        while not self._stop_event.is_set():
            if not self.config.get('services', {}).get('lora_enabled', False):
                time.sleep(5)
                continue

            with self.lora_lock:
                packet = self.rfm9x.receive(timeout=3.0, with_ack=True)

            if not packet: continue

            rssi = self.rfm9x.last_rssi
            try:
                data = json.loads(packet.decode())
                packet_type = data.get('type')

                # We only care about data packets in the base station role
                if self.role == 'base' and packet_type == 'data':
                    self.handle_data_packet(data, rssi)

            except (json.JSONDecodeError, AttributeError):
                print(f"[{self.name}] ERROR: Malformed LoRa packet received.")
            except Exception as e:
                print(f"[{self.name}] ERROR in receive_loop: {e}")

    def handle_data_packet(self, data, rssi):
        station_name = data.get('station_name', 'unknown_station')
        station_id = data.get('station_id')
        payload = data.get('payload', [])

        if not payload or not station_id:
            print(f"[{self.name}] Received data packet with no payload or station_id.")
            return

        print(f"[{self.name}] Received {len(payload)} data records from '{station_name}' (ID: {station_id}) with RSSI: {rssi}")

        # Get the specific database for this remote station
        remote_db = self.get_remote_db(station_name)

        for record in payload:
            # Write to the specific remote DB file
            remote_db.write_reading(
                station_id=record['station_id'],
                sensor=record['sensor'],
                metric=record['metric'],
                value=record['value'],
                rssi=rssi
            )