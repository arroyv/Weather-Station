# handlers.py
import time
import json
import os
import datetime
from threading import Thread, Event, Lock

# Import hardware-specific libraries
try:
    import board
    import busio
    from digitalio import DigitalInOut
    import adafruit_rfm9x
    from Adafruit_IO import Client
    HARDWARE_AVAILABLE = True
except (ImportError, NotImplementedError, NameError):
    print("[Warning] Hardware-specific or Adafruit IO libraries not found. LoRa/AIO will be disabled.")
    HARDWARE_AVAILABLE = False

from database import DatabaseManager # Import DatabaseManager

class BaseHandler(Thread):
    """
    A base class for all handler threads in the application.
    Manages the thread lifecycle, configuration updates, and database connection.
    """
    def __init__(self, config, db_manager):
        super().__init__(daemon=True)
        self.db = db_manager
        self._stop_event = Event()
        self.name = self.__class__.__name__
        self.interval = 300
        self.update_config(config)

    def run(self):
        """The main entry point for the thread."""
        print(f"[{self.name}] Service started.")
        self.loop()
        print(f"[{self.name}] Service stopped.")

    def stop(self):
        """Stops the thread gracefully."""
        self._stop_event.set()
        if hasattr(self, 'close'):
            self.close()

    def update_config(self, new_config):
        """Updates the handler's configuration."""
        self.config = new_config
        self.update_interval()
        print(f"[{self.name}] Configuration updated.")

    def update_interval(self):
        """Placeholder for updating timing intervals from config."""
        raise NotImplementedError

    def loop(self):
        """The main loop for the handler's work."""
        raise NotImplementedError

class AdafruitIOHandler(BaseHandler):
    """
    Handles uploading data to Adafruit IO.
    On a base station, this handler will find all station databases (.db files)
    and upload the latest reading for each sensor metric.
    """
    def __init__(self, config, db_manager, aio_client, aio_prefix):
        self.aio_client = aio_client
        self.aio_prefix = aio_prefix
        self.last_sent_ids = {}
        self._feed_key_cache = {}
        super().__init__(config, db_manager)

    def update_interval(self):
        """Updates the polling interval from the config file."""
        self.interval = self.config.get('timing', {}).get('adafruit_io_interval_seconds', 300)
        self._feed_key_cache = {}

    def _get_feed_key(self, sensor_name, metric_name):
        """
        Determines the Adafruit IO feed key for a given sensor and metric.
        It checks the config for a specific 'feed_key', otherwise creates a default one.
        """
        cache_key = f"{sensor_name}.{metric_name}"
        if cache_key in self._feed_key_cache:
            return self._feed_key_cache[cache_key]
        
        if sensor_name == self.config.get('rain_gauge', {}).get('name'):
            key = self.config['rain_gauge'].get('feed_key')
            if key: self._feed_key_cache[cache_key] = key; return key

        for s_conf in self.config.get('sensors', {}).values():
            if s_conf.get('name') == sensor_name:
                metric_config = s_conf.get('metrics', {}).get(metric_name)
                if metric_config and 'feed_key' in metric_config:
                    key = metric_config['feed_key']; self._feed_key_cache[cache_key] = key; return key
        
        fallback_key = f"{sensor_name}-{metric_name}"; self._feed_key_cache[cache_key] = fallback_key; return fallback_key

    def loop(self):
        """
        Main loop. Periodically scans all .db files, aggregates the latest data from
        all stations, and uploads new readings to Adafruit IO.
        """
        while not self._stop_event.wait(self.interval):
            if not self.config.get('services', {}).get('adafruit_io_enabled', False):
                continue
            
            print(f"[{self.name}] Checking for new data to upload...")

            main_db_path = self.db.db_path
            db_dir = os.path.dirname(main_db_path)
            if not os.path.isdir(db_dir):
                print(f"[{self.name}] Database directory not found, skipping: {db_dir}")
                continue

            all_db_files = [f for f in os.listdir(db_dir) if f.endswith('.db')]
            all_stations_latest_readings = {}

            for db_file in all_db_files:
                try:
                    remote_db_path = os.path.join(db_dir, db_file)
                    temp_db_manager = DatabaseManager(remote_db_path)
                    latest_readings = temp_db_manager.get_latest_readings_by_station()
                    all_stations_latest_readings.update(latest_readings)
                    temp_db_manager.close()
                except Exception as e:
                    print(f"[{self.name}] ERROR reading from {db_file}: {e}")
            
            for station_id, readings in all_stations_latest_readings.items():
                for key, data in readings.items():
                    unique_reading_key = f"station{station_id}-{key}-{data['id']}"
                    if not self.last_sent_ids.get(unique_reading_key):
                        try:
                            feed_key = self._get_feed_key(data['sensor'], data['metric'])
                            if not feed_key: continue
                            
                            full_feed_id = f"{self.aio_prefix}.station-{station_id}.{feed_key}"
                            
                            print(f"[{self.name}] Sending {data['value']:.2f} to {full_feed_id}")
                            self.aio_client.send_data(full_feed_id, data['value'])
                            self.last_sent_ids[unique_reading_key] = True
                        except Exception as e:
                            print(f"[{self.name}] ERROR sending data for {key}: {e}")

class LoRaHandler(BaseHandler):
    """
    Handles LoRa communication. 'remote' role sends data, 'base' role receives.
    """
    def __init__(self, config, db_manager):
        self.last_data_sent_id = 0
        self.rfm9x = None
        self.lora_lock = Lock()
        self.db_connections = {'local': db_manager}
        super().__init__(config, db_manager)

        self.init_lora_hardware()

        if self.rfm9x:
            print(f"[{self.name}] Initialized in '{self.role}' role.")
            if self.role == 'base':
                self.receive_thread = Thread(target=self.receive_loop, daemon=True)
                self.receive_thread.start()
            elif self.role == 'remote':
                self.send_thread = Thread(target=self.send_loop, daemon=True)
                self.send_thread.start()
        else:
            print(f"[{self.name}] LoRa hardware not found or disabled. Handler will be inactive.")

    def init_lora_hardware(self):
        """Initializes the RFM9x LoRa radio hardware."""
        if not HARDWARE_AVAILABLE:
            self.rfm9x = None
            return

        try:
            CS = DigitalInOut(board.CE1)
            RESET = DigitalInOut(board.D25)
            spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)
            self.rfm9x = adafruit_rfm9x.RFM9x(spi, CS, RESET, self.lora_config.get('frequency', 915.0))
            self.rfm9x.tx_power = self.lora_config.get('tx_power', 23)
            
            self.rfm9x.node = self.config.get('station_info', {}).get('station_id', 0)
            if self.role == 'remote':
                self.rfm9x.destination = self.lora_config.get('base_station_address', 1)
            
            print(f"[{self.name}] RFM9x LoRa radio initialized. Node Address: {self.rfm9x.node}, Freq: {self.rfm9x.frequency_mhz}, Power: {self.rfm9x.tx_power}")
        except (ValueError, RuntimeError, FileNotFoundError) as e:
            print(f"[{self.name}] ERROR: RFM9x radio not found or failed to initialize: {e}")
            self.rfm9x = None

    def get_remote_db(self, station_name):
        """Gets or creates a DatabaseManager for a remote station."""
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
        """Closes all remote database connections."""
        print(f"[{self.name}] Closing all database connections.")
        for name, db_conn in self.db_connections.items():
            if name != 'local':
                db_conn.close()

    def update_interval(self):
        """Updates timing and LoRa config from the main config."""
        self.interval = self.config.get('timing', {}).get('transmission_interval_seconds', 60)
        self.lora_config = self.config.get('lora', {})
        self.role = self.lora_config.get('role')

    def loop(self):
        """Main loop waits, as tasks are in dedicated threads."""
        while not self._stop_event.is_set():
            time.sleep(1)

    def send_loop(self):
        """Periodically sends new data from a 'remote' station."""
        if not self.rfm9x: return
        print(f"[{self.name}] Starting send loop.")
        while not self._stop_event.wait(self.interval):
            if not self.config.get('services', {}).get('lora_enabled', False): continue
            self.send_data_payload()

    def send_data_payload(self):
        """Sends a batch of unsent records with acknowledgements."""
        records = self.db.get_unsent_lora_data(self.config['station_info']['station_id'], self.last_data_sent_id)
        if not records: return

        print(f"[{self.name}] Found {len(records)} new records to send.")
        with self.lora_lock:
            for record in records:
                packet = {
                    'type': 'data',
                    'station_name': self.config.get('station_info', {}).get('station_name', 'unknown'),
                    'station_id': self.config.get('station_info', {}).get('station_id', 0),
                    'payload': [dict(record)]
                }
                message = json.dumps(packet).encode("utf-8")
                try:
                    # Set destination for this message
                    self.rfm9x.destination = self.lora_config.get('base_station_address', 1)
                    success = self.rfm9x.send_with_ack(message)
                except Exception as e:
                    print(f"[{self.name}] ERROR: Failed to send message: {e}")
                    success = False
                
                if success:
                    print(f"[{self.name}] Successfully sent record id {record['id']} with ACK.")
                    self.last_data_sent_id = record['id']
                else:
                    print(f"[{self.name}] Failed to send record id {record['id']}. Will retry later.")
                    break # Stop trying for this interval

    def receive_loop(self):
        """Listens for incoming data packets on a 'base' station."""
        if not self.rfm9x: return
        print(f"[{self.name}] Starting receive loop.")
        while not self._stop_event.is_set():
            if not self.config.get('services', {}).get('lora_enabled', False):
                time.sleep(5)
                continue
            
            with self.lora_lock:
                try:
                    packet = self.rfm9x.receive(with_ack=True, timeout=5.0)
                except Exception as e:
                    print(f"[{self.name}] Error during receive: {e}")
                    packet = None

            if not packet: continue

            rssi = self.rfm9x.last_rssi
            try:
                data = json.loads(packet.decode())
                packet_type = data.get('type')
                if packet_type == 'data':
                    self.handle_data_packet(data, rssi)
            except (json.JSONDecodeError, AttributeError):
                print(f"[{self.name}] ERROR: Malformed LoRa packet received (RSSI: {rssi}).")
            except Exception as e:
                print(f"[{self.name}] ERROR in receive_loop: {e}")

    def handle_data_packet(self, data, rssi):
        """Processes a received data packet."""
        station_name = data.get('station_name', 'unknown_station')
        station_id = data.get('station_id')
        payload = data.get('payload', [])

        if not payload or not station_id:
            print(f"[{self.name}] Received data packet with no payload or station_id.")
            return

        remote_db = self.get_remote_db(station_name)
        for record in payload:
            remote_db.write_reading(
                station_id=record['station_id'],
                sensor=record['sensor'],
                metric=record['metric'],
                value=record['value'],
                rssi=rssi
            )
            print(f"[{self.name}] Received id:{record['id']} from '{station_name}' (ID: {station_id}) with RSSI: {rssi}")
