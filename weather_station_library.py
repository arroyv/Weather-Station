# weather_station_library.py (Syntax Corrected)

import os
import time
import datetime
import json
import sqlite3
from threading import Thread, Event, Lock
from Adafruit_IO import Data
import minimalmodbus
from gpiozero import Button

# ============================================================================
# DATA HANDLER PATTERN
# ============================================================================
class DataHandler:
    def process(self, data_packet):
        raise NotImplementedError
    def start(self):
        pass
    def stop(self):
        pass

class AdafruitIOHandler(DataHandler):
    def __init__(self, aio_client, feed_prefix, full_config):
        self.aio_client, self.feed_prefix, self.config = aio_client, feed_prefix, full_config
    def process(self, data_packet):
        print(f"  [AdafruitIOHandler] Sending {sum(len(m) for m in data_packet.values())} data points...")
        for sensor_name, metrics in data_packet.items():
            for metric_name, value in metrics.items():
                try:
                    feed_key = ""
                    if sensor_name == 'rain':
                        feed_key = self.config['rain_gauge'].get('feed_key')
                    else:
                        sensor_addr_str = next((addr for addr, conf in self.config['sensors'].items() if conf['name'] == sensor_name), None)
                        if sensor_addr_str:
                            feed_key = self.config['sensors'][sensor_addr_str]['metrics'][metric_name].get('feed_key')
                    
                    if not feed_key: feed_key = f"{sensor_name}-{metric_name}"

                    full_feed_id = f"{self.feed_prefix}.{feed_key}"
                    self.aio_client.send_data(full_feed_id, value)
                    print(f"    → Sent {value:.2f} to {full_feed_id}")
                except Exception as e:
                    print(f"    → ERROR sending data for {sensor_name}/{metric_name}: {e}")

class SQLiteHandler(DataHandler):
    def __init__(self, db_path):
        self.db_path, self.conn = db_path, None
    def start(self):
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.cursor().execute('''CREATE TABLE IF NOT EXISTS readings (timestamp TEXT, sensor TEXT, metric TEXT, value REAL, PRIMARY KEY (timestamp, sensor, metric))''')
        self.conn.commit()
        print(f"  [SQLiteHandler] Connected to database at {self.db_path}")
    def stop(self):
        if self.conn:
            self.conn.close()
            print("  [SQLiteHandler] Database connection closed.")
    def process(self, data_packet):
        print(f"  [SQLiteHandler] Writing to database...")
        ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        insert_data = [(ts, s, m, v) for s, mets in data_packet.items() for m, v in mets.items()]
        try:
            cur = self.conn.cursor()
            cur.executemany("INSERT INTO readings VALUES (?, ?, ?, ?)", insert_data)
            self.conn.commit()
            print(f"  [SQLiteHandler]   → Wrote {len(insert_data)} records.")
        except sqlite3.Error as e:
            print(f"  [SQLiteHandler]   → ERROR: {e}")

class DataCacheHandler(DataHandler):
    def __init__(self):
        self._cache, self._lock = {}, Lock()
    def process(self, data_packet):
        with self._lock:
            self._cache['timestamp'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            self._cache['sensors'] = data_packet
        print(f"  [DataCacheHandler]   → Latest data cached.")
    def get_latest_data(self):
        with self._lock:
            return self._cache.copy()

# ============================================================================
# WEATHERSTATION CLASS
# ============================================================================
class WeatherStation:
    def __init__(self, config_path='config.json'):
        self.sensors, self.handlers, self._stop_event = {}, [], Event()
        self.config_path, self.last_config_mtime, self.config = config_path, 0, {}
        self.shared_modbus_lock = Lock()
        self.ports_to_scan = []
    def add_sensor(self, name, sensor):
        self.sensors[name] = sensor
    def add_handler(self, handler):
        self.handlers.append(handler)
    def load_config(self):
        print("  [Config] Loading configuration...")
        with open(self.config_path, 'r') as f:
            self.config = json.load(f)
        self.last_config_mtime = os.path.getmtime(self.config_path)
        return self.config
    def start_all(self):
        print("\n--- Starting All Services ---")
        for handler in self.handlers:
            handler.start()
        for sensor in self.sensors.values():
            sensor.start()
        Thread(target=self._data_dispatcher_loop, daemon=True).start()
        Thread(target=self._config_watcher_loop, daemon=True).start()
        Thread(target=self._discovery_loop, daemon=True).start()
    def stop_all(self):
        self._stop_event.set()
        for sensor in self.sensors.values():
            sensor.stop()
        for handler in self.handlers:
            handler.stop()
    def _test_sensor_at_location(self, port, address, baudrate):
        try:
            inst = minimalmodbus.Instrument(port, address)
            inst.serial.baudrate = baudrate; inst.serial.timeout = 2
            _ = inst.read_register(0, 0); return True
        except (IOError, ValueError): return False
    def _data_dispatcher_loop(self):
        upload_rate = self.config.get('upload_rate', 300)
        self._stop_event.wait(10)
        while not self._stop_event.is_set():
            master_packet = {name: readings for name, sensor in self.sensors.items() if (readings := sensor.get_latest_readings())}
            if master_packet:
                print(f"\n{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}: Dispatching data...")
                for handler in self.handlers:
                    try: handler.process(master_packet)
                    except Exception as e: print(f"  → ERROR: Handler {type(handler).__name__} failed: {e}")
            upload_rate = self.config.get('upload_rate', 300)
            self._stop_event.wait(upload_rate)
    def _discovery_loop(self):
        rediscovery_rate = self.config.get('rediscovery_rate', 600)
        print(f"  [Discovery] Re-discovery service started. Will scan every {rediscovery_rate} seconds.")
        while not self._stop_event.is_set():
            self._stop_event.wait(rediscovery_rate)
            if self._stop_event.is_set(): break
            print(f"\n[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [Discovery] Scanning for missing sensors...")
            found_sensor_names = list(self.sensors.keys())
            for addr_str, s_conf in self.config['sensors'].items():
                if s_conf['name'] not in found_sensor_names:
                    print(f"  [Discovery] Looking for missing sensor '{s_conf['name']}'...")
                    addr = int(addr_str)
                    for port in self.ports_to_scan:
                        if self._test_sensor_at_location(port, addr, 4800):
                            print(f"    → SUCCESS: Found new sensor '{s_conf['name']}' on {port}!")
                            sensor = ModbusSensor(name=s_conf['name'], port=port, address=addr, metric_configs=s_conf['metrics'], polling_rate=s_conf['polling_rate'], lock=self.shared_modbus_lock, debug=True)
                            self.add_sensor(s_conf['name'], sensor)
                            sensor.start()
                            break
            print("  [Discovery] Scan complete.")
    def _config_watcher_loop(self):
        while not self._stop_event.is_set():
            try:
                mtime = os.path.getmtime(self.config_path)
                if mtime > self.last_config_mtime:
                    print("\n  [ConfigWatcher] Detected config file change. Reloading...")
                    self.reload_config()
            except OSError as e: print(f"  [ConfigWatcher] ERROR: {e}")
            self._stop_event.wait(30)
    def reload_config(self):
        self.config = self.load_config()
        rediscovery_rate = self.config.get('rediscovery_rate', 600)
        print(f"  [ConfigWatcher] Re-discovery rate updated to {rediscovery_rate} seconds.")
        for sensor_obj in self.sensors.values():
            if hasattr(sensor_obj, 'polling_rate'):
                for conf in self.config['sensors'].values():
                    if conf['name'] == sensor_obj.name:
                        sensor_obj.polling_rate, sensor_obj.metric_configs = conf['polling_rate'], conf['metrics']
                        print(f"    → Updated settings for sensor '{sensor_obj.name}'")
                        break
# ============================================================================
# SENSOR CLASSES
# ============================================================================
class ModbusSensor:
    def __init__(self, name, port, address, metric_configs, polling_rate, **kwargs):
        self.name, self.metric_configs, self.polling_rate = name, metric_configs, polling_rate
        self.instrument = minimalmodbus.Instrument(port, address)
        self.instrument.serial.baudrate, self.instrument.mode = kwargs.get('baudrate', 4800), minimalmodbus.MODE_RTU
        self.debug, self.shared_port_lock = kwargs.get('debug', False), kwargs.get('lock', Lock())
        self.initial_delay, self.min_read_gap = kwargs.get('initial_delay', 2), kwargs.get('min_read_gap', 2)
        self.last_read_time, self._stop_event, self.latest_values, self._value_lock = 0, Event(), None, Lock()
    def start(self):
        if self.debug: print(f"  Starting poller for '{self.name}' (addr {self.instrument.address})")
        Thread(target=self._poll, daemon=True).start()
    def stop(self):
        if self.debug: print(f"  Stopping poller for '{self.name}'...")
        self._stop_event.set()
    def _apply_correction(self, raw, config):
        if not config.get("correction"): return raw
        c = config["correction"]
        if c.get("type") == "map":
            raw_min, raw_max = c.get("raw_min", 0), c.get("raw_max", 1023)
            if (raw_max - raw_min) == 0: return 50.0
            clamped_raw = max(raw_min, min(raw, raw_max))
            return (clamped_raw - raw_min) * 100.0 / (raw_max - raw_min)
        return (raw * c.get("factor", 1.0)) + c.get("offset", 0.0)
    def _poll(self):
        time.sleep(self.initial_delay)
        while not self._stop_event.is_set():
            if time.time() - self.last_read_time >= self.min_read_gap:
                with self.shared_port_lock:
                    self.last_read_time = time.time()
                    try:
                        values = []
                        for config in self.metric_configs.values():
                            read_function_name = config.get("function", "read_register")
                            read_function = getattr(self.instrument, read_function_name)
                            if read_function_name == 'read_long':
                                raw_value = read_function(registeraddress=config["register"])
                            else:
                                raw_value = read_function(registeraddress=config["register"], number_of_decimals=config.get("decimals", 0), signed=config.get("signed", False))
                            values.append(self._apply_correction(raw_value, config))
                        with self._value_lock: self.latest_values = values
                    except (IOError, ValueError) as e: print(f"ERROR: Read failed for '{self.name}': {e}")
            self._stop_event.wait(self.polling_rate)
    def get_latest_readings(self):
        with self._value_lock:
            if self.latest_values is None: return {}
            return dict(zip(self.metric_configs.keys(), [round(v, 2) for v in self.latest_values]))

class RainGaugeSensor:
    def __init__(self, name, metric, gpio_pin, mm_per_tip, **kwargs):
        self.name, self.metric, self.gpio_pin, self.mm_per_tip = name, metric, gpio_pin, mm_per_tip
        self.debounce_s = kwargs.get('debounce_ms', 250) / 1000.0
        self.debug = kwargs.get('debug', False)
        self.tip_count, self._count_lock, self._stop_event = 0, Lock(), Event()
        self.button = Button(self.gpio_pin, pull_up=True, bounce_time=self.debounce_s)
    def start(self):
        if self.debug: print(f"  Starting RainGauge on GPIO {self.gpio_pin} (using gpiozero default backend)...")
        self.button.when_pressed = self._tip_callback
        Thread(target=self._daily_reset_thread, daemon=True).start()
    def stop(self):
        if self.debug: print("  Stopping RainGaugeSensor...")
        self._stop_event.set()
        self.button.close()
    def _tip_callback(self):
        with self._count_lock:
            self.tip_count += 1
            if self.debug: print(f"  [Tipped!] Rain gauge on GPIO {self.gpio_pin}. Total today: {self.tip_count}")
    def _daily_reset_thread(self):
        while not self._stop_event.is_set():
            now = datetime.datetime.now()
            next_midnight = (now + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=1)
            if self._stop_event.wait((next_midnight - now).total_seconds()): break
            with self._count_lock: self.tip_count = 0
            if self.debug: print(f"  [RainGauge] Daily tip count reset for GPIO {self.gpio_pin}.")
    def get_latest_readings(self):
        with self._count_lock:
            return {self.metric: round(self.tip_count * self.mm_per_tip, 2)}