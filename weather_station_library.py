# weather_station_library.py
import os
import time
import datetime
import json
from threading import Thread, Event, Lock
import minimalmodbus
from gpiozero import Button

# ============================================================================
# WEATHERSTATION CLASS
# ============================================================================
class WeatherStation:
    def __init__(self, config_path='config.json', db_manager=None):
        self.sensors, self._stop_event = {}, Event()
        self.config_path, self.last_config_mtime, self.config = config_path, 0, {}
        self.shared_modbus_lock = Lock()
        self.db_manager = db_manager
        if not self.db_manager:
            raise ValueError("A DatabaseManager instance is required.")
        self.station_id = 0

    def add_sensor(self, name, sensor):
        self.sensors[name] = sensor

    def load_config(self):
        print("  [Config] Loading configuration...")
        with open(self.config_path, 'r') as f:
            self.config = json.load(f)
        self.last_config_mtime = os.path.getmtime(self.config_path)
        self.station_id = self.config.get('station_info', {}).get('station_id', 0)
        return self.config

    def discover_and_add_sensors(self):
        """Scans for and adds all sensors from the config file."""
        config = self.config
        ports_to_scan = [
            '/dev/ttyUSB0', '/dev/ttyUSB1', '/dev/ttyUSB2',
            '/dev/ttyACM0', '/dev/ttyACM1', '/dev/ttyACM2', '/dev/ttyACM3','/dev/ttyS0', '/dev/serial0'
        ]
        
        print(f"  [Discovery] Performing initial discovery of Modbus sensors...")
        found_addrs = {}
        for addr_str, s_conf in config['sensors'].items():
            addr = int(addr_str)
            for port in ports_to_scan:
                if os.path.exists(port):
                    if self._test_sensor_at_location(port, addr, 4800):
                        print(f"    → Found '{s_conf['name']}' (addr {addr}) on {port}")
                        found_addrs[addr] = port
                        break

        for addr, port in found_addrs.items():
            s_conf = config['sensors'][str(addr)]
            sensor = ModbusSensor(
                name=s_conf['name'], port=port, address=addr,
                metric_configs=s_conf['metrics'], polling_rate=s_conf['polling_rate'],
                lock=self.shared_modbus_lock, debug=True
            )
            self.add_sensor(s_conf['name'], sensor)

        if 'rain_gauge' in config:
            rg_conf = config['rain_gauge']
            rain_sensor = RainGaugeSensor(
                name=rg_conf['name'], metric=rg_conf['metric'],
                gpio_pin=rg_conf['gpio_pin'], mm_per_tip=rg_conf['mm_per_tip'],
                debug=True, debounce_ms=rg_conf['debounce_ms']
            )
            self.add_sensor(rg_conf['name'], rain_sensor)

    def start_all(self):
        print("\n--- Starting Data Collection Service ---")
        for sensor in self.sensors.values():
            sensor.start()
        Thread(target=self._data_collector_loop, daemon=True).start()
        Thread(target=self._config_watcher_loop, daemon=True).start()

    def stop_all(self):
        self._stop_event.set()
        for sensor in self.sensors.values():
            sensor.stop()

    def _test_sensor_at_location(self, port, address, baudrate):
        try:
            with self.shared_modbus_lock:
                inst = minimalmodbus.Instrument(port, address)
                inst.serial.baudrate = baudrate
                inst.serial.timeout = 2
                _ = inst.read_register(0, 0)
            return True
        except (IOError, ValueError):
            return False

    def _data_collector_loop(self):
        """
        This loop is now much simpler. It just collects data from sensors
        and writes it to the database.
        """
        # Use a shorter, more frequent interval for data collection
        collection_interval = 30 
        print(f"[Collector] Starting data collection loop (interval: {collection_interval}s).")
        
        self._stop_event.wait(5) # Initial delay
        while not self._stop_event.is_set():
            master_packet = {name: sensor.get_latest_readings() for name, sensor in self.sensors.items()}
            
            if master_packet:
                print(f"\n[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [Collector] Writing data to database...")
                for sensor_name, metrics in master_packet.items():
                    for metric_name, value in metrics.items():
                        if value is not None:
                            self.db_manager.write_reading(self.station_id, sensor_name, metric_name, value)
                            print(f"  → Logged: {sensor_name}/{metric_name} = {value}")
            
            self._stop_event.wait(collection_interval)

    def _config_watcher_loop(self):
        """Monitors the config file for changes and reloads settings."""
        while not self._stop_event.is_set():
            try:
                mtime = os.path.getmtime(self.config_path)
                if mtime > self.last_config_mtime:
                    print("\n[ConfigWatcher] Detected config file change. Reloading sensor settings...")
                    self.reload_config()
            except OSError as e:
                print(f"[ConfigWatcher] ERROR: {e}")
            self._stop_event.wait(10)
            
    def reload_config(self):
        self.load_config()
        # Update settings for running sensors
        for sensor_obj in self.sensors.values():
            if hasattr(sensor_obj, 'polling_rate'):
                for conf in self.config['sensors'].values():
                    if conf['name'] == sensor_obj.name:
                        sensor_obj.polling_rate = conf['polling_rate']
                        sensor_obj.metric_configs = conf['metrics']
                        print(f"    → Updated settings for sensor '{sensor_obj.name}'")
                        break

# ============================================================================
# SENSOR CLASSES (Largely unchanged, but simplified)
# ============================================================================
class ModbusSensor:
    def __init__(self, name, port, address, metric_configs, polling_rate, **kwargs):
        self.name, self.metric_configs, self.polling_rate = name, metric_configs, polling_rate
        self.instrument = minimalmodbus.Instrument(port, address)
        self.instrument.serial.baudrate = 4800
        self.instrument.mode = minimalmodbus.MODE_RTU
        self.debug = kwargs.get('debug', False)
        self.shared_port_lock = kwargs.get('lock', Lock())
        self._stop_event, self.latest_values, self._value_lock = Event(), {}, Lock()

    def start(self):
        if self.debug: print(f"  [Sensor] Starting poller for '{self.name}'")
        Thread(target=self._poll, daemon=True).start()

    def stop(self):
        if self.debug: print(f"  [Sensor] Stopping poller for '{self.name}'")
        self._stop_event.set()

    def _apply_correction(self, raw, config):
        # Correction logic remains the same
        if "correction" not in config: return raw
        c = config["correction"]
        if c.get("type") == "map":
            raw_min, raw_max = c.get("raw_min", 0), c.get("raw_max", 1023)
            if (raw_max - raw_min) == 0: return 50.0
            clamped_raw = max(raw_min, min(raw, raw_max))
            return (clamped_raw - raw_min) * 100.0 / (raw_max - raw_min)
        return (raw * c.get("factor", 1.0)) + c.get("offset", 0.0)

    def _poll(self):
        time.sleep(2) # Initial delay
        while not self._stop_event.is_set():
            with self.shared_port_lock:
                try:
                    current_values = {}
                    for metric_name, config in self.metric_configs.items():
                        read_func_name = config.get("function", "read_register")
                        read_func = getattr(self.instrument, read_func_name)
                        
                        raw_value = read_func(
                            registeraddress=config["register"],
                            number_of_decimals=config.get("decimals", 0),
                            signed=config.get("signed", False)
                        )
                        
                        corrected_value = self._apply_correction(raw_value, config)
                        current_values[metric_name] = round(corrected_value, 2)

                    with self._value_lock:
                        self.latest_values = current_values

                except (IOError, ValueError) as e:
                    print(f"ERROR: Read failed for '{self.name}': {e}")
            
            self._stop_event.wait(self.polling_rate)

    def get_latest_readings(self):
        with self._value_lock:
            return self.latest_values.copy()


class RainGaugeSensor:
    def __init__(self, name, metric, gpio_pin, mm_per_tip, **kwargs):
        self.name, self.metric, self.gpio_pin, self.mm_per_tip = name, metric, gpio_pin, mm_per_tip
        self.debounce_s = kwargs.get('debounce_ms', 250) / 1000.0
        self.debug = kwargs.get('debug', False)
        self.tip_count, self._count_lock, self._stop_event = 0, Lock(), Event()
        self.button = Button(self.gpio_pin, pull_up=True, bounce_time=self.debounce_s)
        self.last_reported_count = 0

    def start(self):
        if self.debug: print(f"  [Sensor] Starting RainGauge on GPIO {self.gpio_pin}")
        self.button.when_pressed = self._tip_callback
    
    def stop(self):
        if self.debug: print(f"  [Sensor] Stopping RainGaugeSensor")
        self._stop_event.set()
        self.button.close()

    def _tip_callback(self):
        with self._count_lock:
            self.tip_count += 1
            if self.debug: print(f"  [Tipped!] Rain gauge. Total tips: {self.tip_count}")

    def get_latest_readings(self):
        with self._count_lock:
            # Report the number of new tips since the last read
            new_tips = self.tip_count - self.last_reported_count
            self.last_reported_count = self.tip_count
            return {self.metric: round(new_tips * self.mm_per_tip, 4)}

