# handlers.py
import time
import json
import requests # Used for WiFi sync, but not in this version
from threading import Thread, Event
# NOTE: You will need to install a LoRa library, e.g., 'pip install pyLora'
# And then import it here. For now, we simulate it.
# from pyLora import LoRa

class BaseHandler(Thread):
    """Base class for services that handle data after it's in the database."""
    def __init__(self, config, db_manager):
        super().__init__(daemon=True)
        self.db = db_manager
        self._stop_event = Event()
        self.name = self.__class__.__name__
        self.interval = 300 # Default interval
        self.update_config(config) # Set initial config and interval

    def run(self):
        print(f"[{self.name}] Service started.")
        self.loop()
        print(f"[{self.name}] Service stopped.")

    def stop(self):
        self._stop_event.set()
        self.join() # Wait for the thread to finish

    def update_config(self, new_config):
        """Updates the handler's configuration."""
        self.config = new_config
        self.update_interval()
        print(f"[{self.name}] Configuration updated. New interval: {self.interval}s")

    def update_interval(self):
        """To be implemented by subclasses to set their specific loop interval."""
        raise NotImplementedError

    def loop(self):
        """The main loop for the handler. To be implemented by subclasses."""
        raise NotImplementedError

class AdafruitIOHandler(BaseHandler):
    """
    Reads the latest data from the database and sends it to Adafruit IO.
    """
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
            if key:
                self._feed_key_cache[cache_key] = key
                return key

        for sensor_config in self.config.get('sensors', {}).values():
            if sensor_config.get('name') == sensor_name:
                metric_config = sensor_config.get('metrics', {}).get(metric_name)
                if metric_config and 'feed_key' in metric_config:
                    key = metric_config['feed_key']
                    self._feed_key_cache[cache_key] = key
                    return key
        
        fallback_key = f"{sensor_name}-{metric_name}"
        self._feed_key_cache[cache_key] = fallback_key
        return fallback_key

    def loop(self):
        while not self._stop_event.wait(self.interval):
            if not self.config.get('services', {}).get('adafruit_io_enabled', False):
                continue

            print(f"[{self.name}] Checking for new data to upload...")
            latest_readings = self.db.get_latest_readings()
            
            for key, data in latest_readings.items():
                record_id = data['id']
                if self.last_sent_ids.get(key) != record_id:
                    try:
                        sensor_name = data['sensor']
                        metric_name = data['metric']
                        feed_key = self._get_feed_key(sensor_name, metric_name)
                        
                        if not feed_key:
                            continue

                        full_feed_id = f"{self.aio_prefix}.{feed_key}"
                        
                        print(f"[{self.name}] Sending {data['value']:.2f} to {full_feed_id}")
                        self.aio_client.send_data(full_feed_id, data['value'])
                        self.last_sent_ids[key] = record_id
                    except Exception as e:
                        print(f"[{self.name}] ERROR sending data for {key}: {e}")


class LoRaHandler(BaseHandler):
    """
    Handles sending (remote role) and receiving (base role) data via LoRa.
    """
    def __init__(self, config, db_manager):
        # last_sent_id tracks the last record ID sent from this station's DB
        self.last_sent_id = 0 
        super().__init__(config, db_manager)
        
        # --- PLACEHOLDER for actual LoRa hardware setup ---
        # self.lora = LoRa(device=self.lora_config.get('device'), freq=self.lora_config.get('frequency'))
        # self.lora.set_addr(self.lora_config.get('local_address'))
        print(f"[{self.name}] Initialized. (SIMULATED LoRa)")
        # --- END PLACEHOLDER ---
        
        # Start the appropriate loop based on role
        if self.role == 'base':
            self.receive_thread = Thread(target=self.receive_loop, daemon=True)
            self.receive_thread.start()
        elif self.role == 'remote':
            self.send_thread = Thread(target=self.send_loop, daemon=True)
            self.send_thread.start()

    def update_interval(self):
        self.interval = self.config.get('timing', {}).get('transmission_interval_seconds', 60)
        self.lora_config = self.config.get('lora', {})
        self.station_id = self.config.get('station_info', {}).get('station_id', 0)
        self.role = self.lora_config.get('role')

    def loop(self):
        """The main loop just keeps the thread alive. Work is done in send/receive loops."""
        while not self._stop_event.is_set():
            time.sleep(1)

    def send_loop(self):
        """This loop is for SENDING data (for 'remote' stations)."""
        print(f"[{self.name}] Starting send loop (interval: {self.interval}s).")
        while not self._stop_event.wait(self.interval):
            if not self.config.get('services', {}).get('lora_enabled', False):
                continue

            # Get all data for THIS station that hasn't been sent yet
            records_to_send = self.db.get_unsent_lora_data(self.station_id, self.last_sent_id)
            if not records_to_send:
                continue

            # Convert sqlite3.Row objects to plain dictionaries for JSON serialization
            payload = [dict(row) for row in records_to_send]
            
            print(f"[{self.name}] Preparing to send {len(payload)} records via LoRa...")
            try:
                # --- PLACEHOLDER for sending ---
                # self.lora.send_to(json.dumps(payload).encode(), self.lora_config.get('remote_address'))
                print(f"[{self.name}] SIMULATING LORA SEND: {json.dumps(payload)}")
                # --- END PLACEHOLDER ---
                
                # If send was successful, update the last sent ID
                self.last_sent_id = payload[-1]['id']

            except Exception as e:
                print(f"[{self.name}] ERROR sending LoRa data: {e}")


    def receive_loop(self):
        """This loop is for RECEIVING data (for 'base' stations)."""
        print(f"[{self.name}] Starting receive loop.")
        while not self._stop_event.is_set():
            if not self.config.get('services', {}).get('lora_enabled', False):
                time.sleep(5)
                continue

            try:
                # --- PLACEHOLDER for receiving ---
                # has_message, payload, rssi, snr = self.lora.receive()
                # if has_message:
                #     data_batch = json.loads(payload.decode())
                # --- END PLACEHOLDER ---
                
                # SIMULATION: To test, you can manually create a fake payload here
                # For example:
                # data_batch = [{'id': 1, 'timestamp': '2025-07-11T16:00:00Z', 'station_id': 2, 'sensor': 'soil', 'metric': 'temp-c', 'value': 25.5}]
                # rssi = -55
                
                # For now, we'll just simulate that we don't receive anything
                has_message = False
                if not has_message:
                    time.sleep(2) # Don't busy-wait
                    continue

                print(f"[{self.name}] Received LoRa packet with RSSI: {rssi}. Contains {len(data_batch)} records.")
                
                for record in data_batch:
                    self.db.write_reading(
                        station_id=record['station_id'],
                        sensor=record['sensor'],
                        metric=record['metric'],
                        value=record['value'],
                        rssi=rssi,
                        timestamp=record['timestamp'] # Use the original timestamp
                    )
                print(f"[{self.name}] Successfully logged {len(data_batch)} records from remote station.")

            except json.JSONDecodeError:
                print(f"[{self.name}] ERROR: Received malformed JSON in LoRa packet.")
            except Exception as e:
                print(f"[{self.name}] ERROR in receive loop: {e}")
