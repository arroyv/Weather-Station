# handlers.py
import time
import json
import requests # Used for WiFi sync
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
        # A cache to store looked-up feed keys to avoid repeated searching
        self._feed_key_cache = {}
        super().__init__(config, db_manager)

    def update_interval(self):
        self.interval = self.config.get('timing', {}).get('adafruit_io_interval_seconds', 300)
        # Clear the cache when config is updated so keys are re-read
        self._feed_key_cache = {}

    def _get_feed_key(self, sensor_name, metric_name):
        """
        Looks up the specific feed_key from the config file.
        Caches results for efficiency.
        """
        cache_key = f"{sensor_name}.{metric_name}"
        if cache_key in self._feed_key_cache:
            return self._feed_key_cache[cache_key]

        # Handle rain gauge as a special case
        if sensor_name == self.config.get('rain_gauge', {}).get('name'):
            key = self.config['rain_gauge'].get('feed_key')
            if key:
                self._feed_key_cache[cache_key] = key
                return key

        # Search through the modbus sensors
        for sensor_config in self.config.get('sensors', {}).values():
            if sensor_config.get('name') == sensor_name:
                metric_config = sensor_config.get('metrics', {}).get(metric_name)
                if metric_config and 'feed_key' in metric_config:
                    key = metric_config['feed_key']
                    self._feed_key_cache[cache_key] = key
                    return key
        
        # Fallback if no specific key is found
        print(f"[{self.name}] WARNING: No specific 'feed_key' found for {sensor_name}/{metric_name}. Building one from names.")
        fallback_key = f"{sensor_name}-{metric_name}"
        self._feed_key_cache[cache_key] = fallback_key
        return fallback_key

    def loop(self):
        while not self._stop_event.wait(self.interval):
            if not self.config.get('services', {}).get('adafruit_io_enabled', False):
                continue # Skip if disabled

            print(f"[{self.name}] Checking for new data to upload...")
            latest_readings = self.db.get_latest_readings()
            
            for key, data in latest_readings.items():
                record_id = data['id']
                if self.last_sent_ids.get(key) != record_id:
                    try:
                        # --- FIX: Look up the feed_key from the config instead of just building it. ---
                        sensor_name = data['sensor']
                        metric_name = data['metric']
                        
                        feed_key = self._get_feed_key(sensor_name, metric_name)
                        
                        if not feed_key:
                            print(f"[{self.name}] ERROR: Could not determine feed key for {sensor_name}/{metric_name}. Skipping.")
                            continue

                        full_feed_id = f"{self.aio_prefix}.{feed_key}"
                        
                        print(f"[{self.name}] Sending {data['value']:.2f} to {full_feed_id}")
                        self.aio_client.send_data(full_feed_id, data['value'])
                        self.last_sent_ids[key] = record_id
                    except Exception as e:
                        print(f"[{self.name}] ERROR sending data for {key}: {e}")


class LoRaHandler(BaseHandler):
    """
    Handles sending and receiving data via LoRa.
    """
    def __init__(self, config, db_manager):
        self.last_sent_id = 0
        super().__init__(config, db_manager)
        if self.role == 'base':
            Thread(target=self.receive_loop, daemon=True).start()

    def update_interval(self):
        self.interval = self.config.get('timing', {}).get('transmission_interval_seconds', 600)
        self.lora_config = self.config.get('lora', {})
        self.station_id = self.config.get('station_info', {}).get('station_id', 0)
        self.role = self.lora_config.get('role')

    def loop(self):
        """This loop is for SENDING data (for 'remote' stations)."""
        while not self._stop_event.is_set():
            # Use a short sleep here and check the main interval inside the loop
            # This makes the service more responsive to the stop event.
            if self._stop_event.wait(self.interval):
                break

            if not self.config.get('services', {}).get('lora_enabled', False) or self.role != 'remote':
                continue

            latest_readings = self.db.get_latest_readings()
            if latest_readings:
                key = sorted(latest_readings.keys())[0]
                data_to_send = latest_readings[key]
                if data_to_send['id'] > self.last_sent_id:
                    payload = json.dumps(data_to_send)
                    print(f"[{self.name}] SIMULATING LORA SEND: {payload}")
                    self.last_sent_id = data_to_send['id']

    def receive_loop(self):
        """This loop is for RECEIVING data (for 'base' stations)."""
        print(f"[{self.name}] Listening for incoming LoRa data...")
        while not self._stop_event.is_set():
            if self.config.get('services', {}).get('lora_enabled', False) and self.role == 'base':
                # Placeholder for actual LoRa receiving logic
                pass
            time.sleep(5)

class WiFiSyncHandler(BaseHandler):
    """
    Periodically sends unsynced data to a central server.
    """
    def update_interval(self):
        self.interval = self.config.get('timing', {}).get('transmission_interval_seconds', 600)
        self.sync_config = self.config.get('wifi_sync', {})
        self.target_url = self.sync_config.get('target_url')

    def loop(self):
        while not self._stop_event.wait(self.interval):
            if not self.config.get('services', {}).get('wifi_sync_enabled', False) or not self.target_url:
                continue

            unsynced_rows = self.db.get_unsynced_data(limit=100)
            if not unsynced_rows:
                print(f"[{self.name}] No new data to sync.")
                continue

            payload = [dict(row) for row in unsynced_rows]
            record_ids = [row['id'] for row in unsynced_rows]
            
            print(f"[{self.name}] Attempting to sync {len(payload)} records to {self.target_url}...")
            try:
                response = requests.post(self.target_url, json=payload, timeout=15)
                if response.status_code == 200:
                    print(f"[{self.name}] Sync successful.")
                    self.db.mark_data_as_synced(record_ids)
                else:
                    print(f"[{self.name}] ERROR: Sync failed. Server returned status {response.status_code}: {response.text}")
            except requests.RequestException as e:
                print(f"[{self.name}] ERROR: Could not connect to sync server: {e}")
