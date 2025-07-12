# weather_station_library.py
import os
import time
from threading import Thread, Event, Lock

# Import hardware-specific libraries
try:
    import minimalmodbus
    from gpiozero import Button
    HARDWARE_AVAILABLE = True
except (ImportError, NotImplementedError):
    print("[Warning] Hardware-specific libraries not found. Sensors will be disabled.")
    HARDWARE_AVAILABLE = False

class WeatherStation:
    def __init__(self, initial_config, db_manager=None):
        self.sensors = {}
        self._stop_event = Event()
        self.shared_modbus_lock = Lock()
        self.db_manager = db_manager
        if not self.db_manager:
            raise ValueError("A DatabaseManager instance is required.")
        
        self.config = initial_config
        self.station_id = self.config.get('station_info', {}).get('station_id', 0)

    def discover_and_add_sensors(self):
        if not HARDWARE_AVAILABLE:
            print("  [Discovery] Skipped due to missing hardware libraries.")
            return

        config = self.config
        ports_to_scan = ['/dev/ttyACM0', '/dev/ttyACM1', '/dev/ttyACM2', '/dev/ttyACM3']
        
        print("  [Discovery] Performing initial discovery of Modbus sensors...")
        found_addrs = {}
        for addr_str, s_conf in config.get('sensors', {}).items():
            if not s_conf.get('enabled', False):
                continue
            addr = int(addr_str)
            for port in ports_to_scan:
                if os.path.exists(port) and self._test_sensor_at_location(port, addr):
                    print(f"  [Discovery] Found '{s_conf['name']}' (addr {addr}) on {port}")
                    found_addrs[addr] = port
                    break
        
        for addr, port in found_addrs.items():
            s_conf = config['sensors'][str(addr)]
            sensor = ModbusSensor(port, addr, s_conf, lock=self.shared_modbus_lock, db_manager=self.db_manager, station_id=self.station_id, debug=True)
            self.sensors[s_conf['name']] = sensor

        rg_conf = config.get('rain_gauge')
        if rg_conf and rg_conf.get('enabled', False):
            rain_sensor = RainGaugeSensor(rg_conf, db_manager=self.db_manager, station_id=self.station_id, debug=True)
            self.sensors[rg_conf['name']] = rain_sensor

    def start(self):
        print("\n--- Starting Sensor Polling Services ---")
        for sensor in self.sensors.values():
            sensor.start()

    def stop(self):
        self._stop_event.set()
        for sensor in self.sensors.values():
            sensor.stop()

    def update_config(self, new_config):
        self.config = new_config
        # This is a simplified update. A more robust implementation would handle
        # adding/removing sensors without a full restart.
        for sensor in self.sensors.values():
            if hasattr(sensor, 'name'):
                # Find corresponding config for Modbus sensors
                for s_conf in self.config.get('sensors', {}).values():
                    if s_conf['name'] == sensor.name:
                        sensor.update_config(s_conf)
                        break
                # Find config for rain gauge
                rg_conf = self.config.get('rain_gauge', {})
                if rg_conf.get('name') == sensor.name:
                    sensor.update_config(rg_conf)


    def _test_sensor_at_location(self, port, address):
        try:
            with self.shared_modbus_lock:
                inst = minimalmodbus.Instrument(port, address)
                inst.serial.baudrate = 4800
                inst.serial.timeout = 1.0
                inst.read_register(0, 0) # Try reading a common register
            return True
        except (IOError, ValueError):
            return False

class ModbusSensor:
    def __init__(self, port, address, initial_config, **kwargs):
        self.instrument = minimalmodbus.Instrument(port, address)
        self.instrument.serial.baudrate = 4800
        self.instrument.mode = minimalmodbus.MODE_RTU
        self.debug = kwargs.get('debug', False)
        self.shared_port_lock = kwargs.get('lock', Lock())
        self._stop_event = Event()
        
        self.db_manager = kwargs.get('db_manager')
        self.station_id = kwargs.get('station_id')
        if not self.db_manager:
            raise ValueError("ModbusSensor requires a db_manager instance.")
        
        self.poller_thread = None
        self.update_config(initial_config)

    def update_config(self, new_config):
        self.name = new_config['name']
        self.metric_configs = new_config['metrics']
        self.polling_rate = new_config.get('polling_rate', 600)
        self.enabled = new_config.get('enabled', False)
        if self.debug: print(f"[{self.name}] Config updated. Polling rate: {self.polling_rate}s. Enabled: {self.enabled}")

    def start(self):
        if self.enabled:
            self.poller_thread = Thread(target=self._poll, daemon=True)
            self.poller_thread.start()

    def stop(self):
        self._stop_event.set()
        if self.poller_thread and self.poller_thread.is_alive():
            self.poller_thread.join()

    def _poll(self):
        while not self._stop_event.wait(self.polling_rate):
            if not self.enabled: continue
            with self.shared_port_lock:
                try:
                    for metric_name, config in self.metric_configs.items():
                        read_func_name = config.get("function", "read_register")
                        read_func = getattr(self.instrument, read_func_name)
                        
                        raw_value = read_func(
                            registeraddress=config["register"],
                            number_of_decimals=config.get("decimals", 0),
                            signed=config.get("signed", False)
                        )
                        
                        if raw_value is not None:
                            self.db_manager.write_reading(self.station_id, self.name, metric_name, raw_value)
                            if self.debug: print(f"[{self.name}] Logged: {metric_name} = {raw_value:.2f}")
                except (IOError, ValueError) as e:
                    print(f"[{self.name}] ERROR: Read failed: {e}")

class RainGaugeSensor:
    def __init__(self, initial_config, **kwargs):
        self.debug = kwargs.get('debug', False)
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
        if self.debug: print(f"[{self.name}] Config updated. Enabled: {self.enabled}")

    def start(self):
        if self.enabled:
            self.button.when_pressed = self._tip_callback
    
    def stop(self):
        self.button.close()

    def _tip_callback(self):
        if self.enabled:
            self.db_manager.write_reading(self.station_id, self.name, self.metric, self.mm_per_tip)
            if self.debug: print(f"[{self.name}] Logged: Rain gauge tipped!")
