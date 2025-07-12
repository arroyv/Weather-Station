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
        """Receives a new config object and updates settings for running sensors."""
        self.config = new_config
        self.station_id = self.config.get('station_info', {}).get('station_id', 0)
        
        # Update polling rates and status for all running Modbus sensors
        for sensor_obj in self.sensors.values():
            if isinstance(sensor_obj, ModbusSensor):
                sensor_found_in_config = False
                for s_conf in self.config.get('sensors', {}).values():
                    if s_conf['name'] == sensor_obj.name:
                        sensor_obj.update_config(s_conf)
                        print(f"Updated settings for sensor '{sensor_obj.name}'")
                        sensor_found_in_config = True
                        break
                if not sensor_found_in_config:
                     sensor_obj.stop() # Stop sensor if removed from config, though not ideal
        print("[WeatherStation] Configuration updated.")

    def discover_and_add_sensors(self):
        """Scans for and adds all enabled sensors from the config file."""
        config = self.config
        ports_to_scan = [
            # USB to Serial Converters
            # '/dev/ttyUSB0', '/dev/ttyUSB1', '/dev/ttyUSB2', '/dev/ttyUSB3',
            '/dev/ttyACM0', '/dev/ttyACM1', '/dev/ttyACM2', '/dev/ttyACM3',

            # On-board Hardware UARTs
            # '/dev/ttyS0',
            # '/dev/ttyAMA0', '/dev/ttyAMA1', '/dev/ttyAMA2', '/dev/ttyAMA3', '/dev/ttyAMA4',

            # Symbolic Links
            # '/dev/serial0',
            # '/dev/serial1'/
        ]
        
        print(f"  [Discovery] Performing initial discovery of Modbus sensors...")
        found_addrs = {}
        for addr_str, s_conf in config.get('sensors', {}).items():
            # --- NEW: Check if sensor is enabled before discovering ---
            if not s_conf.get('enabled', False):
                print(f"Sensor '{s_conf['name']}' is disabled. Skipping.")
                continue

            addr = int(addr_str)
            for port in ports_to_scan:
                if os.path.exists(port):
                    if self._test_sensor_at_location(port, addr, 4800):
                        print(f"Found '{s_conf['name']}' (addr {addr}) on {port}")
                        found_addrs[addr] = port
                        break

        for addr, port in found_addrs.items():
            s_conf = config['sensors'][str(addr)]
            sensor = ModbusSensor(
                port=port, address=addr,
                initial_config=s_conf, # Pass the whole sensor config
                lock=self.shared_modbus_lock, debug=True,
                db_manager=self.db_manager, station_id=self.station_id
            )
            self.add_sensor(s_conf['name'], sensor)

        rg_conf = config.get('rain_gauge')
        if rg_conf and rg_conf.get('enabled', False):
            rain_sensor = RainGaugeSensor(
                initial_config=rg_conf, debug=True,
                db_manager=self.db_manager, station_id=self.station_id
            )
            self.add_sensor(rg_conf['name'], rain_sensor)
        elif rg_conf:
            print(f"Sensor '{rg_conf['name']}' is disabled. Skipping.")


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
    def __init__(self, port, address, initial_config, **kwargs):
        self.instrument = minimalmodbus.Instrument(port, address)
        self.instrument.serial.baudrate = 4800
        self.instrument.mode = minimalmodbus.MODE_RTU
        self.debug = kwargs.get('debug', False)
        self.shared_port_lock = kwargs.get('lock', Lock())
        self._stop_event = Event()
        self.poller_thread = None
        
        self.db_manager = kwargs.get('db_manager')
        self.station_id = kwargs.get('station_id')
        if not self.db_manager:
            raise ValueError("ModbusSensor requires a db_manager instance.")
        
        self.update_config(initial_config)

    def update_config(self, new_config):
        """Updates sensor's specific configuration."""
        self.name = new_config['name']
        self.metric_configs = new_config['metrics']
        self.polling_rate = new_config.get('polling_rate', 600)
        self.enabled = new_config.get('enabled', False)

    def start(self):
        if self.enabled:
            if self.debug: print(f"  [Sensor] Starting poller for '{self.name}' (interval: {self.polling_rate}s)")
            self._stop_event.clear()
            self.poller_thread = Thread(target=self._poll, daemon=True)
            self.poller_thread.start()

    def stop(self):
        if self.debug: print(f"  [Sensor] Stopping poller for '{self.name}'")
        self._stop_event.set()
        if self.poller_thread:
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
        time.sleep(2) 
        while not self._stop_event.is_set():
            if not self.enabled:
                self._stop_event.wait(5) # If disabled, just wait
                continue

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
                        
                        if corrected_value is not None:
                            self.db_manager.write_reading(self.station_id, self.name, metric_name, corrected_value)
                            if self.debug: print(f"Logged: {self.name}/{metric_name} = {corrected_value:.2f}")
                except (IOError, ValueError) as e:
                    print(f"ERROR: Read failed for '{self.name}': {e}")
            
            self._stop_event.wait(self.polling_rate)

class RainGaugeSensor:
    def __init__(self, initial_config, **kwargs):
        self.debug = kwargs.get('debug', False)
        self._stop_event = Event()
        
        self.db_manager = kwargs.get('db_manager')
        self.station_id = kwargs.get('station_id')
        if not self.db_manager:
            raise ValueError("RainGaugeSensor requires a db_manager instance.")

        self.update_config(initial_config)
        self.button = Button(self.gpio_pin, pull_up=True, bounce_time=self.debounce_ms / 1000.0)

    def update_config(self, new_config):
        self.name = new_config['name']
        self.metric = new_config['metric']
        self.gpio_pin = new_config['gpio_pin']
        self.mm_per_tip = new_config['mm_per_tip']
        self.debounce_ms = new_config.get('debounce_ms', 250)
        self.enabled = new_config.get('enabled', False)

    def start(self):
        if self.enabled:
            if self.debug: print(f"  [Sensor] Starting RainGauge on GPIO {self.gpio_pin}")
            self.button.when_pressed = self._tip_callback
    
    def stop(self):
        if self.debug: print(f"  [Sensor] Stopping RainGaugeSensor")
        self._stop_event.set()
        self.button.close()

    def _tip_callback(self):
        if self.enabled:
            tip_value = self.mm_per_tip
            self.db_manager.write_reading(self.station_id, self.name, self.metric, tip_value)
            if self.debug: print(f"Logged: [Tipped!] Rain gauge event. Value: {tip_value}")
