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

    def add_sensor(self, name, sensor):
        self.sensors[name] = sensor

    def update_config(self, new_config):
        """Receives a new config object and updates its settings."""
        self.config = new_config
        self.station_id = self.config.get('station_info', {}).get('station_id', 0)
        
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
                lock=self.shared_modbus_lock, debug=True,
                # Pass the db manager and station ID to the sensor itself
                db_manager=self.db_manager, station_id=self.station_id
            )
            self.add_sensor(s_conf['name'], sensor)

        if 'rain_gauge' in config:
            rg_conf = config['rain_gauge']
            rain_sensor = RainGaugeSensor(
                name=rg_conf['name'], metric=rg_conf['metric'],
                gpio_pin=rg_conf['gpio_pin'], mm_per_tip=rg_conf['mm_per_tip'],
                debug=True, debounce_ms=rg_conf['debounce_ms'],
                # Pass the db manager and station ID to the sensor itself
                db_manager=self.db_manager, station_id=self.station_id
            )
            self.add_sensor(rg_conf['name'], rain_sensor)

    def start(self):
        print("\n--- Starting Sensor Polling Services ---")
        for sensor in self.sensors.values():
            sensor.start()

    def stop(self):
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

# ============================================================================
# SENSOR CLASSES
# ============================================================================
class ModbusSensor:
    def __init__(self, name, port, address, metric_configs, polling_rate, **kwargs):
        self.name, self.metric_configs, self.polling_rate = name, metric_configs, polling_rate
        self.instrument = minimalmodbus.Instrument(port, address)
        self.instrument.serial.baudrate = 4800
        self.instrument.mode = minimalmodbus.MODE_RTU
        self.debug = kwargs.get('debug', False)
        self.shared_port_lock = kwargs.get('lock', Lock())
        self._stop_event = Event()
        self.poller_thread = None
        
        # Sensor now needs to know about the database to write to it.
        self.db_manager = kwargs.get('db_manager')
        self.station_id = kwargs.get('station_id')
        if not self.db_manager:
            raise ValueError("ModbusSensor requires a db_manager instance.")

    def start(self):
        if self.debug: print(f"  [Sensor] Starting poller for '{self.name}' (interval: {self.polling_rate}s)")
        self.poller_thread = Thread(target=self._poll, daemon=True)
        self.poller_thread.start()

    def stop(self):
        if self.debug: print(f"  [Sensor] Stopping poller for '{self.name}'")
        self._stop_event.set()
        self.poller_thread.join()

    def _apply_correction(self, raw, config):
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
                        
                        # --- NEW: Write directly to the database ---
                        if corrected_value is not None:
                            self.db_manager.write_reading(self.station_id, self.name, metric_name, corrected_value)
                            if self.debug: print(f"  → Logged: {self.name}/{metric_name} = {corrected_value:.2f}")

                except (IOError, ValueError) as e:
                    print(f"ERROR: Read failed for '{self.name}': {e}")

class RainGaugeSensor:
    def __init__(self, name, metric, gpio_pin, mm_per_tip, **kwargs):
        self.name, self.metric, self.gpio_pin, self.mm_per_tip = name, metric, gpio_pin, mm_per_tip
        self.debounce_s = kwargs.get('debounce_ms', 250) / 1000.0
        self.debug = kwargs.get('debug', False)
        self._stop_event = Event()
        self.button = Button(self.gpio_pin, pull_up=True, bounce_time=self.debounce_s)

        # Sensor now needs to know about the database to write to it.
        self.db_manager = kwargs.get('db_manager')
        self.station_id = kwargs.get('station_id')
        if not self.db_manager:
            raise ValueError("RainGaugeSensor requires a db_manager instance.")

    def start(self):
        if self.debug: print(f"  [Sensor] Starting RainGauge on GPIO {self.gpio_pin}")
        self.button.when_pressed = self._tip_callback
    
    def stop(self):
        if self.debug: print(f"  [Sensor] Stopping RainGaugeSensor")
        self._stop_event.set()
        self.button.close()

    def _tip_callback(self):
        # --- NEW: Log each tip event directly to the database ---
        tip_value = self.mm_per_tip
        self.db_manager.write_reading(self.station_id, self.name, self.metric, tip_value)
        if self.debug: print(f"  → Logged: [Tipped!] Rain gauge event. Value: {tip_value}")
