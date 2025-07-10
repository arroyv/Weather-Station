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
        self.config = config
        self.db = db_manager
        self._stop_event = Event()
        self.name = self.__class__.__name__

    def run(self):
        print(f"[{self.name}] Service started.")
        self.loop()
        print(f"[{self.name}] Service stopped.")

    def stop(self):
        self._stop_event.set()

    def loop(self):
        """The main loop for the handler. To be implemented by subclasses."""
        raise NotImplementedError

class AdafruitIOHandler(BaseHandler):
    """
    Reads the latest data from the database and sends it to Adafruit IO.
    This is now a standalone service.
    """
    def __init__(self, config, db_manager, aio_client, aio_prefix):
        super().__init__(config, db_manager)
        self.aio_client = aio_client
        self.aio_prefix = aio_prefix
        self.upload_interval = config.get('upload_rate', 300)
        self.last_sent_ids = {} # Tracks the last sent reading ID for each metric

    def loop(self):
        while not self._stop_event.wait(self.upload_interval):
            print(f"[{self.name}] Checking for new data to upload...")
            latest_readings = self.db.get_latest_readings()
            
            for key, data in latest_readings.items():
                record_id = data['id']
                # Only send if it's a new reading we haven't sent before
                if self.last_sent_ids.get(key) != record_id:
                    try:
                        # Construct the feed key
                        feed_key = f"{data['sensor']}-{data['metric']}"
                        full_feed_id = f"{self.aio_prefix}.{feed_key}"
                        
                        print(f"[{self.name}] Sending {data['value']:.2f} to {full_feed_id}")
                        self.aio_client.send_data(full_feed_id, data['value'])
                        self.last_sent_ids[key] = record_id
                    except Exception as e:
                        print(f"[{self.name}] ERROR sending data for {key}: {e}")

class LoRaHandler(BaseHandler):
    """
    Handles sending and receiving data via LoRa.
    The behavior depends on the 'role' in the config ('remote' or 'base').
    """
    def __init__(self, config, db_manager):
        super().__init__(config, db_manager)
        self.lora_config = config.get('lora', {})
        self.station_id = config.get('station_info', {}).get('station_id', 0)
        self.role = self.lora_config.get('role')
        self.last_sent_id = 0 # Track the last reading ID sent

        # --- PLACEHOLDER for actual LoRa hardware setup ---
        # You would initialize your LoRa object here, for example:
        # self.lora = LoRa(device=self.lora_config.get('device'), freq=self.lora_config.get('frequency'))
        # self.lora.set_addr(self.lora_config.get('local_address'))
        print(f"[{self.name}] Initialized in '{self.role}' role. (SIMULATED)")
        # --- END PLACEHOLDER ---

        if self.role == 'base':
            # A base station needs a thread to listen for incoming data
            Thread(target=self.receive_loop, daemon=True).start()

    def loop(self):
        """This loop is for SENDING data (primarily for 'remote' stations)."""
        if self.role != 'remote':
            return # Base stations only listen in this design, but could also send.

        while not self._stop_event.wait(60): # Check for new data every minute
            latest_readings = self.db.get_latest_readings()
            # We'll just send the latest reading from the first sensor for this example
            if latest_readings:
                # Get the first item, sort by key to be deterministic
                key = sorted(latest_readings.keys())[0]
                data_to_send = latest_readings[key]
                
                if data_to_send['id'] > self.last_sent_id:
                    payload = json.dumps(data_to_send)
                    print(f"[{self.name}] SIMULATING SEND: {payload}")
                    # --- PLACEHOLDER for sending ---
                    # self.lora.send_to(payload.encode(), self.lora_config.get('remote_address'))
                    # --- END PLACEHOLDER ---
                    self.last_sent_id = data_to_send['id']

    def receive_loop(self):
        """This loop is for RECEIVING data (for 'base' stations)."""
        print(f"[{self.name}] Listening for incoming LoRa data...")
        while not self._stop_event.is_set():
            # --- PLACEHOLDER for receiving ---
            # This is where you would block and wait for a LoRa message
            # has_message, payload, rssi, snr = self.lora.receive()
            # if has_message:
            #     try:
            #         data = json.loads(payload.decode())
            #         print(f"[{self.name}] Received data with RSSI: {rssi}: {data}")
            #         # Write the received data to the base station's own database
            #         self.db.write_reading(
            #             station_id=data['station_id'],
            #             sensor=data['sensor'],
            #             metric=data['metric'],
            #             value=data['value'],
            #             rssi=rssi
            #         )
            #     except (json.JSONDecodeError, KeyError) as e:
            #         print(f"[{self.name}] ERROR: Could not parse received LoRa packet: {e}")
            # --- END PLACEHOLDER ---
            time.sleep(5) # Simulate checking for messages

class WiFiSyncHandler(BaseHandler):
    """
    Periodically sends unsynced data from the local database to a central server (Jetson Nano).
    """
    def __init__(self, config, db_manager):
        super().__init__(config, db_manager)
        self.sync_config = config.get('wifi_sync', {})
        self.target_url = self.sync_config.get('target_url')

    def loop(self):
        while not self._stop_event.wait(300): # Attempt to sync every 5 minutes
            if not self.target_url:
                print(f"[{self.name}] No target_url configured. Skipping sync.")
                continue

            unsynced_rows = self.db.get_unsynced_data(limit=100)
            if not unsynced_rows:
                print(f"[{self.name}] No new data to sync.")
                continue

            # Convert sqlite3.Row objects to plain dictionaries
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

