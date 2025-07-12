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
        self.last_config_sent_time = 0
        self.rfm9x = None
        self.lora_lock = Lock()
        super().__init__(config, db_manager)
        
        self.init_lora_hardware()

        if self.rfm9x:
            print(f"[{self.name}] Initialized in '{self.role}' role.")
            self.receive_thread = Thread(target=self.receive_loop, daemon=True)
            self.receive_thread.start()
            if self.role in ['base', 'remote']:
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
            # Set addressing
            self.rfm9x.node = self.lora_config.get('local_address', 1)
            self.rfm9x.destination = self.lora_config.get('remote_address', 2)
            print(f"[{self.name}] RFM9x LoRa radio initialized. Freq: {self.rfm9x.frequency_mhz}, Power: {self.rfm9x.tx_power}")
        except (ValueError, RuntimeError) as e:
            print(f"[{self.name}] ERROR: RFM9x radio not found or failed to initialize: {e}")
            self.rfm9x = None

    def update_interval(self):
        self.interval = self.config.get('timing', {}).get('transmission_interval_seconds', 60)
        self.time_sync_interval = self.config.get('timing', {}).get('lora_time_sync_interval_seconds', 3600)
        self.lora_config = self.config.get('lora', {})
        self.role = self.lora_config.get('role')

    def loop(self):
        while not self._stop_event.is_set(): time.sleep(1)

    def send_loop(self):
        if not self.rfm9x: return
        print(f"[{self.name}] Starting send loop.")
        last_time_sync = 0
        while not self._stop_event.wait(self.interval):
            if not self.config.get('services', {}).get('lora_enabled', False): continue
            
            if self.role == 'remote':
                self.send_data_payload()
            elif self.role == 'base':
                if time.time() - last_time_sync > self.time_sync_interval:
                    self.send_time_sync_payload()
                    last_time_sync = time.time()

    def send_data_payload(self):
        records = self.db.get_unsent_lora_data(self.config['station_info']['station_id'], self.last_data_sent_id)
        if not records: return
        packet = {'type': 'data', 'payload': [dict(r) for r in records]}
        print(f"[{self.name}] Sending {len(records)} data records.")
        with self.lora_lock:
            print(packet)
            self.rfm9x.send(json.dumps(packet).encode("utf-8"))
        self.last_data_sent_id = records[-1]['id']

    def send_time_sync_payload(self):
        packet = {'type': 'time_sync', 'payload': datetime.datetime.now(datetime.timezone.utc).isoformat()}
        print(f"[{self.name}] Sending time sync packet.")
        with self.lora_lock:
            self.rfm9x.send(json.dumps(packet).encode("utf-8"))

    def receive_loop(self):
        if not self.rfm9x: return
        print(f"[{self.name}] Starting receive loop.")
        while not self._stop_event.is_set():
            if not self.config.get('services', {}).get('lora_enabled', False): time.sleep(5); continue
            
            with self.lora_lock:
                packet = self.rfm9x.receive(timeout=5.0)
            
            if not packet: continue

            rssi = self.rfm9x.last_rssi
            try:
                data = json.loads(packet.decode())
                packet_type = data.get('type')
                payload = data.get('payload')

                if self.role == 'base' and packet_type == 'data':
                    self.handle_data_packet(payload, rssi)
                elif self.role == 'remote' and packet_type == 'time_sync':
                    self.handle_time_sync_packet(payload)

            except (json.JSONDecodeError, AttributeError): print(f"[{self.name}] ERROR: Malformed LoRa packet received.")
            except Exception as e: print(f"[{self.name}] ERROR in receive_loop: {e}")

    def handle_data_packet(self, payload, rssi):
        print(f"[{self.name}] Received {len(payload)} data records with RSSI: {rssi}")
        for record in payload:
            self.db.write_reading(station_id=record['station_id'], sensor=record['sensor'], metric=record['metric'], value=record['value'], rssi=rssi)

    def handle_time_sync_packet(self, payload):
        print(f"[{self.name}] Received time sync packet: {payload}. Updating system time.")
        try:
            os.system(f"sudo date -s '{payload}'")
        except Exception as e:
            print(f"[{self.name}] ERROR setting system time. Ensure passwordless sudo is configured. {e}")