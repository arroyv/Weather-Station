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
    def __init__(self, initial_config, db_manager=None):
        self.sensors, self._stop_event = {}, Event()
        self.shared_modbus_lock = Lock()
        self.db_manager = db_manager
        if not self.db_manager:
            raise ValueError("A DatabaseManager instance is required.")
        
        self.config = initial_config
        self.station_id = self.config.get('station_info', {}).get('station_id', 0)
        self.collection_interval = self.config.get('timing', {}).get('collection_interval_seconds', 600)

    def add_sensor(self, name, sensor):
        self.sensors[name] = sensor

    def update_config(self, new_config):
        """Receives a new config object and updates its settings."""
        self.config = new_config
        self.station_id = self.config.get('station_info', {}).get('station_id', 0)
        self.collection_interval = self.config.get('timing', {}).get('collection_interval_seconds', 600)
        
        # Update polling rates for all running Modbus sensors
        for sensor_obj in self.sensors.values():
            if isinstance(sensor_obj, ModbusSensor):
                for conf in self.config.get('sensors', {}).values():
                    if conf['name'] == sensor_obj.name:
                        sensor_obj.polling_rate = conf['polling_rate']
                        sensor_obj.metric_configs = conf['metrics']
                        print(f"    → Updated polling rate for '{sensor_obj.name}' to {sensor_obj.polling_rate}s")
                        break
        print("[WeatherStation] Configuration updated.")

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

    def start(self):
        print("\n--- Starting Data Collection Service ---")
        for sensor in self.sensors.values():
            sensor.start()
        self.collector_thread = Thread(target=self._data_collector_loop, daemon=True)
        self.collector_thread.start()

    def stop(self):
        self._stop_event.set()
        for sensor in self.sensors.values():
            sensor.stop()
        self.collector_thread.join()

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
        Collects data from sensors and writes it to the database at the configured interval.
        """
        print(f"[Collector] Starting data collection loop (initial interval: {self.collection_interval}s).")
        
        self._stop_event.wait(5) # Initial delay
        while not self._stop_event.wait(self.collection_interval):
            master_packet = {name: sensor.get_latest_readings() for name, sensor in self.sensors.items()}
            
            if master_packet:
                print(f"\n[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [Collector] Writing data to database...")
                for sensor_name, metrics in master_packet.items():
                    for metric_name, value in metrics.items():
                        if value is not None:
                            self.db_manager.write_reading(self.station_id, sensor_name, metric_name, value)
                            print(f"  → Logged: {sensor_name}/{metric_name} = {value}")

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
        self.poller_thread = None

    def start(self):
        if self.debug: print(f"  [Sensor] Starting poller for '{self.name}'")
        self.poller_thread = Thread(target=self._poll, daemon=True)
        self.poller_thread.start()

    def stop(self):
        if self.debug: print(f"  [Sensor] Stopping poller for '{self.name}'")
        self._stop_event.set()
        self.poller_thread.join()

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
        while not self._stop_event.wait(self.polling_rate):
            with self.shared_port_lock:
                try:
                    current_values = {}
                    for metric_name, config in self.metric_configs.items():
                        read_func_name = config.get("function", "read_register")
                        read_func = getattr(self.instrument, read_func_name)
                        
                        if read_func_name == 'read_long':
                            raw_value = read_func(registeraddress=config["register"])
                        else:
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
