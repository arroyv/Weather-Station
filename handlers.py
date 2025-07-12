# handlers.py
import time
import os
import datetime
import msgpack
from threading import Thread, Event, Lock

import board
import busio
from digitalio import DigitalInOut
import adafruit_rfm9x

from database import DatabaseManager

class BaseHandler(Thread):
    def __init__(self, config, db_manager):
        # This direct call to Thread.__init__ with keyword arguments is the correct pattern
        # and fixes the AssertionError.
        super().__init__(daemon=True)
        self.db = db_manager
        self._stop_event = Event()
        self.name = self.__class__.__name__
        self.update_config(config)

    def run(self):
        print(f"[{self.name}] Service started.")
        self.loop()
        print(f"[{self.name}] Service stopped.")

    def stop(self):
        self._stop_event.set()
        if hasattr(self, 'close'):
            self.close()
        if self.is_alive():
            self.join()

    def update_config(self, new_config):
        self.config = new_config
        self.update_interval()
        print(f"[{self.name}] Configuration updated for {self.name}.")

    def update_interval(self):
        # This should be implemented by subclasses
        pass

    def loop(self):
        raise NotImplementedError

class AdafruitIOHandler(BaseHandler):
    def __init__(self, config, db_manager, aio_client, aio_prefix):
        self.aio_client = aio_client
        self.aio_prefix = aio_prefix
        self.last_sent_ids = {}
        super().__init__(config, db_manager)

    def update_interval(self):
        self.interval = self.config.get('timing', {}).get('adafruit_io_interval_seconds', 300)

    def loop(self):
        # ... Adafruit IO loop logic ...
        pass

class LoRaHandler(BaseHandler):
    def __init__(self, config, db_manager):
        self.last_data_sent_id = 0
        self.rfm9x = None
        self.lora_lock = Lock()
        self.db_connections = {'local': db_manager}
        # This call now correctly inherits from the fixed BaseHandler
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
            
            self.rfm9x.enable_crc = True
            self.rfm9x.ack_retries = self.lora_config.get('ack_retries', 3)
            self.rfm9x.ack_delay = self.lora_config.get('ack_delay', 0.2)
            self.rfm9x.ack_timeout = self.lora_config.get('ack_timeout', 2.0)
            
            self.rfm9x.node = self.lora_config.get('local_address')
            self.rfm9x.destination = self.lora_config.get('remote_address')
            
            print(f"[{self.name}] RFM9x LoRa radio initialized. Node {self.rfm9x.node} -> Dest {self.rfm9x.destination}")
        except Exception as e:
            print(f"[{self.name}] ERROR: RFM9x radio not found: {e}")
            self.rfm9x = None

    def get_remote_db(self, station_name):
        if station_name in self.db_connections:
            return self.db_connections[station_name]
        
        main_db_path = self.db_connections['local'].db_path
        base_dir = os.path.dirname(main_db_path)
        remote_db_path = os.path.join(base_dir, f"{station_name}.db")
        
        db_manager = DatabaseManager(remote_db_path)
        self.db_connections[station_name] = db_manager
        return db_manager

    def close(self):
        for name, db_conn in self.db_connections.items():
            if name != 'local':
                db_conn.close()

    def update_interval(self):
        self.interval = self.config.get('timing', {}).get('transmission_interval_seconds', 30)
        self.lora_config = self.config.get('lora', {})
        self.role = self.lora_config.get('role')

    def loop(self):
        while not self._stop_event.is_set(): time.sleep(1)

    def send_loop(self):
        if not self.rfm9x: return
        while not self._stop_event.wait(self.interval):
            if not self.config.get('services', {}).get('lora_enabled', False): continue
            if self.role == 'remote':
                self.send_data_payload()

    def send_data_payload(self):
        records = self.db.get_unsent_lora_data(self.config['station_info']['station_id'], self.last_data_sent_id)
        if not records: return

        payload_records = [dict(r) for r in records]

        packet = {
            'type': 'data',
            'station_name': self.config.get('station_info', {}).get('station_name'),
            'station_id': self.config.get('station_info', {}).get('station_id'),
            'payload': payload_records
        }
        
        with self.lora_lock:
            packed_data = msgpack.packb(packet)
            if len(packed_data) > 252:
                print(f"ERROR: Packet size ({len(packed_data)}) exceeds LoRa limit.")
                return

            print(f"[{self.name}] Sending {len(records)} records with ACK...")
            success = self.rfm9x.send_with_ack(packed_data)
            
            if success:
                print(f"[{self.name}] ACK received.")
                self.last_data_sent_id = records[-1]['id']
            else:
                print(f"[{self.name}] No ACK received.")

    def receive_loop(self):
        if not self.rfm9x: return
        while not self._stop_event.is_set():
            if not (self.config.get('services', {}).get('lora_enabled', False) and self.role == 'base'):
                time.sleep(5)
                continue
            
            packet = self.rfm9x.receive(timeout=5.0, with_ack=True)
            if not packet: continue

            rssi = self.rfm9x.last_rssi
            try:
                data = msgpack.unpackb(packet, raw=False)
                if data.get('type') == 'data':
                    self.handle_data_packet(data, rssi)
            except Exception as e:
                print(f"[{self.name}] ERROR in receive_loop: {e}")

    def handle_data_packet(self, data, rssi):
        station_name = data.get('station_name')
        station_id = data.get('station_id')
        payload = data.get('payload', [])
        
        if not all([station_name, station_id is not None, payload]):
            print(f"[{self.name}] Received invalid data packet.")
            return

        remote_db = self.get_remote_db(station_name)
        
        for record in payload:
            remote_db.write_reading(
                station_id=station_id,
                sensor=record['sensor'],
                metric=record['metric'],
                value=record['value'],
                rssi=rssi,
                timestamp=record['timestamp']
            )
        print(f"[{self.name}] Wrote {len(payload)} records from '{station_name}'")