# #weather_station.py
# import minimalmodbus
# import time
# from threading import Thread, Event, Lock
# from Adafruit_IO import Client

# class Sensor:
#     def __init__(self, port='/dev/ttyAMA0', address=1, baudrate=4800, polling_rate=2, print_rate=5*60, debug=False, initial_delay=0, feed_names=["default_feed"], log_to_adafruit_flag=True, print_to_terminal_flag=True, lock=None, min_read_gap=0):
#         self.instrument = minimalmodbus.Instrument(port, address)
#         self.instrument.serial.baudrate = baudrate
#         self.instrument.serial.bytesize = 8
#         self.instrument.serial.parity = minimalmodbus.serial.PARITY_NONE
#         self.instrument.serial.stopbits = 1
#         self.instrument.serial.timeout = 3  # Increase timeout to 2 seconds
#         self.polling_rate = polling_rate  # Rate for sending data to Adafruit IO
#         self.print_rate = print_rate  # Rate for printing to the terminal
#         self.debug = debug
#         self.initial_delay = initial_delay
#         self.feed_names = feed_names  # List of feed names to log data to
#         self.log_to_adafruit_flag = log_to_adafruit_flag  # Flag to control logging
#         self.print_to_terminal_flag = print_to_terminal_flag  # Flag to control printing to terminal
#         self.active = False
#         self._stop_event = Event()
#         self.lock = lock  # Shared lock for port synchronization
#         self.min_read_gap = min_read_gap  # Minimum gap between consecutive reads
#         self.last_read_time = 0  # Track the last time the sensor was read

#     def start(self):
#         if self.debug:
#             print(f"Starting {self.__class__.__name__} sensor polling after {self.initial_delay} seconds.")
#         self.active = True
#         self._stop_event.clear()
#         Thread(target=self._poll).start()

#     def stop(self):
#         if self.debug:
#             print(f"Stopping {self.__class__.__name__} sensor polling.")
#         self.active = False
#         self._stop_event.set()

#     def _poll(self):
#         time.sleep(self.initial_delay)  # Apply initial delay before the first read
#         last_print_time = 0  # Track last time data was printed
#         last_log_time = 0  # Track last time data was logged to Adafruit IO

#         while not self._stop_event.is_set():
#             current_time = time.time()

#             # Ensure minimum time gap between reads to prevent overlap
#             if current_time - self.last_read_time >= self.min_read_gap:
#                 # Acquire the lock before reading the sensor
#                 with self.lock:
#                     data = self.read()  # Data is a list of numeric values
#                     self.last_read_time = current_time  # Update the last read time

#                     # Log data to Adafruit IO based on polling_rate
#                     if data and self.log_to_adafruit_flag and current_time - last_log_time >= self.polling_rate:
#                         self.log_to_adafruit(data)
#                         last_log_time = current_time

#                     # Print data to terminal based on print_rate if flag is enabled
#                     if current_time - last_print_time >= self.print_rate and data and self.print_to_terminal_flag:
#                         self.print_to_terminal(data)
#                         last_print_time = current_time

#             time.sleep(1)  # Sleep briefly to avoid hogging the CPU

#     def log_to_adafruit(self, data):
#         # Log each value to its respective feed
#         for value, feed_name in zip(data, self.feed_names):
#             self.log_data(feed_name, value)

#     def print_to_terminal(self, data):
#         # Print data to the terminal
#         print(f"Sensor {self.__class__.__name__}: {data}")

#     def read(self):
#         raise NotImplementedError("This method should be implemented by subclasses")

#     def log_data(self, feed_name, value):
#         # Log numeric values to Adafruit IO feed
#         self.aio_client.send_data(feed_name, value)
#         print(f"Logged value {value} to feed {feed_name}")

# class AtmosphericPressureSensor(Sensor):
#     def read(self):
#         try:
#             pressure = self.instrument.read_register(0x0000, 1)  # Numeric value
#             temperature = self.instrument.read_register(0x0001, 1, signed=True)  # Numeric value
#             if self.debug:
#                 print(f"Pressure: {pressure}, Temperature: {temperature}")
#             return [pressure, temperature]  # Return as a list of numeric values
#         except IOError as e:
#             print(f"Failed to read from AtmosphericPressureSensor: {e}")
#             return []

# class AtmosphericTemperatureHumiditySensor(Sensor):
#     def read(self):
#         try:
#             humidity = self.instrument.read_register(0x0000, 1)  # Numeric value
#             temperature = self.instrument.read_register(0x0001, 1, signed=True)  # Numeric value
#             if self.debug:
#                 print(f"Humidity: {humidity}, Temperature: {temperature}")
#             return [humidity, temperature]  # Return as a list of numeric values
#         except IOError as e:
#             print(f"Failed to read from AtmosphericTemperatureHumiditySensor: {e}")
#             return []

# class CO2Sensor(Sensor):
#     def read(self):
#         try:
#             co2_concentration = self.instrument.read_register(0x0002, 0)  # Numeric value
#             if self.debug:
#                 print(f"CO2 Concentration: {co2_concentration}")
#             return [co2_concentration]  # Return as a list with one numeric value
#         except IOError as e:
#             print(f"Failed to read from CO2Sensor: {e}")
#             return []

# class LightSensor(Sensor):
#     def read(self):
#         try:
#             light_intensity = self.instrument.read_register(0x0006, 0)  # Numeric value
#             if self.debug:
#                 print(f"Light Intensity: {light_intensity}")
#             return [light_intensity]  # Return as a list with one numeric value
#         except IOError as e:
#             print(f"Failed to read from LightSensor: {e}")
#             return []

# class WindDirectionSensor(Sensor):
#     def __init__(self, port='/dev/ttyAMA0', address=6, baudrate=4800, polling_rate=2, print_rate=5*60, debug=False, initial_delay=0, feed_names=["default_feed"], log_to_adafruit_flag=True, print_to_terminal_flag=True, lock=None, min_read_gap=0):
#         super().__init__(port, address, baudrate, polling_rate, print_rate, debug, initial_delay, feed_names, log_to_adafruit_flag, print_to_terminal_flag, lock, min_read_gap)
#         self.direction_map = {
#             0: "North",
#             45: "Northeast",
#             90: "East",
#             135: "Southeast",
#             180: "South",
#             225: "Southwest",
#             270: "West",
#             315: "Northwest"
#         }

#     def read(self):
#         try:
#             wind_direction_degrees = self.instrument.read_register(0x0001, 0)  # Numeric value
#             direction = self.direction_map.get(wind_direction_degrees, "Unknown Direction")
#             if self.debug:
#                 print(f"Wind Direction: {wind_direction_degrees} ({direction})")
#             return [wind_direction_degrees]  # Return as a list with one numeric value
#         except IOError as e:
#             print(f"Failed to read from WindDirectionSensor: {e}")
#             return []

# class WindSpeedSensor(Sensor):
#     def read(self):
#         try:
#             wind_speed = self.instrument.read_register(0x0000, 1)  # Numeric value
#             if self.debug:
#                 print(f"Wind Speed: {wind_speed}")
#             return [wind_speed]  # Return as a list with one numeric value
#         except IOError as e:
#             print(f"Failed to read from WindSpeedSensor: {e}")
#             return []

# class WeatherStation:
#     def __init__(self, aio_client, print_rate=5*60, print_to_terminal_flag=True):
#         self.sensors = {}
#         self.aio_client = aio_client
#         self.print_rate = print_rate  # Rate for printing to the terminal
#         self.print_to_terminal_flag = print_to_terminal_flag  # Flag to control terminal printing

#     def add_sensor(self, name, sensor):
#         self.sensors[name] = sensor
#         sensor.aio_client = self.aio_client  # Pass the Adafruit IO client to each sensor

#     def start_all(self):
#         for sensor_name, sensor in self.sensors.items():
#             # Start each sensor with its own polling rate and initial delay
#             sensor.start()

#     def stop_all(self):
#         for sensor in self.sensors.values():
#             sensor.stop()


# # weather_station.py

# import minimalmodbus
# import time
# import datetime
# from threading import Thread, Event, Lock
# from Adafruit_IO import Client
# import RPi.GPIO as GPIO

# class Sensor:
#     def __init__(self,
#                  port='/dev/ttyAMA0',
#                  address=1,
#                  baudrate=4800,
#                  polling_rate=2,
#                  print_rate=5 * 60,
#                  debug=False,
#                  initial_delay=0,
#                  feed_names=["default_feed"],
#                  log_to_adafruit_flag=True,
#                  print_to_terminal_flag=True,
#                  lock=None,
#                  min_read_gap=0):
#         """
#         Base class for all Modbus‐based sensors.
#         """
#         # Initialize minimalmodbus instrument
#         self.instrument = minimalmodbus.Instrument(port, address)
#         self.instrument.serial.baudrate = baudrate
#         self.instrument.serial.bytesize = 8
#         self.instrument.serial.parity = minimalmodbus.serial.PARITY_NONE
#         self.instrument.serial.stopbits = 1
#         self.instrument.serial.timeout = 3  # seconds

#         # Timing and flags
#         self.polling_rate = polling_rate      # seconds between each Adafruit IO update
#         self.print_rate = print_rate          # seconds between each terminal print
#         self.debug = debug
#         self.initial_delay = initial_delay    # seconds before first read
#         self.feed_names = feed_names          # list of feed names (one per returned value)
#         self.log_to_adafruit_flag = log_to_adafruit_flag
#         self.print_to_terminal_flag = print_to_terminal_flag

#         # Thread control
#         self.active = False
#         self._stop_event = Event()

#         # For port synchronization (if multiple sensors share the same serial port)
#         self.lock = lock
#         self.min_read_gap = min_read_gap      # minimum seconds between consecutive reads
#         self.last_read_time = 0

#     def start(self):
#         if self.debug:
#             print(f"Starting {self.__class__.__name__} (address {self.instrument.address}) in {self.initial_delay}s...")
#         self.active = True
#         self._stop_event.clear()
#         Thread(target=self._poll, daemon=True).start()

#     def stop(self):
#         if self.debug:
#             print(f"Stopping {self.__class__.__name__} (address {self.instrument.address})...")
#         self.active = False
#         self._stop_event.set()

#     def _poll(self):
#         """
#         Core polling loop. Respects initial_delay, min_read_gap, polling_rate, and print_rate.
#         """
#         time.sleep(self.initial_delay)
#         last_print_time = 0
#         last_log_time = 0

#         while not self._stop_event.is_set():
#             now = time.time()
#             if now - self.last_read_time >= self.min_read_gap:
#                 # Acquire lock if provided
#                 if self.lock:
#                     with self.lock:
#                         data = self.read()
#                 else:
#                     data = self.read()

#                 self.last_read_time = now

#                 # Log to Adafruit IO if needed
#                 if (data
#                     and self.log_to_adafruit_flag
#                     and (now - last_log_time >= self.polling_rate)):
#                     self.log_to_adafruit(data)
#                     last_log_time = now

#                 # Print to terminal if needed
#                 if (data
#                     and self.print_to_terminal_flag
#                     and (now - last_print_time >= self.print_rate)):
#                     self.print_to_terminal(data)
#                     last_print_time = now

#             time.sleep(1)

#     def read(self):
#         """
#         Must be implemented by each subclass to return a list of numeric values.
#         """
#         raise NotImplementedError("Subclasses must implement read()")

#     def log_to_adafruit(self, data):
#         """
#         Send each element of data to its corresponding feed name.
#         """
#         for value, feed_name in zip(data, self.feed_names):
#             self.log_data(feed_name, value)

#     def print_to_terminal(self, data):
#         print(f"{self.__class__.__name__} data: {data}")

#     def log_data(self, feed_name, value):
#         """
#         Send a single numeric value to an Adafruit IO feed.
#         """
#         self.aio_client.send_data(feed_name, value)
#         print(f"  → Logged {value} to '{feed_name}'")


# class AtmosphericPressureSensor(Sensor):
#     def read(self):
#         try:
#             pressure = self.instrument.read_register(0x0000, 1)           # e.g., hPa
#             temperature = self.instrument.read_register(0x0001, 1, True)  # signed, e.g., °C
#             if self.debug:
#                 print(f"  [PressureSensor] P={pressure} hPa, T={temperature} °C")
#             return [pressure, temperature]
#         except IOError as e:
#             print(f"Failed to read AtmosphericPressureSensor: {e}")
#             return []


# class AtmosphericTemperatureHumiditySensor(Sensor):
#     def read(self):
#         try:
#             humidity = self.instrument.read_register(0x0000, 1)           # e.g., %RH
#             temperature = self.instrument.read_register(0x0001, 1, True)  # e.g., °C
#             if self.debug:
#                 print(f"  [TempHumSensor] H={humidity}%RH, T={temperature}°C")
#             return [humidity, temperature]
#         except IOError as e:
#             print(f"Failed to read AtmosphericTemperatureHumiditySensor: {e}")
#             return []


# class CO2Sensor(Sensor):
#     def read(self):
#         try:
#             co2 = self.instrument.read_register(0x0002, 0)  # e.g., ppm
#             if self.debug:
#                 print(f"  [CO2Sensor] CO2={co2} ppm")
#             return [co2]
#         except IOError as e:
#             print(f"Failed to read CO2Sensor: {e}")
#             return []


# class LightSensor(Sensor):
#     def read(self):
#         try:
#             light = self.instrument.read_register(0x0006, 0)  # e.g., lux
#             if self.debug:
#                 print(f"  [LightSensor] LUX={light}")
#             return [light]
#         except IOError as e:
#             print(f"Failed to read LightSensor: {e}")
#             return []


# class WindDirectionSensor(Sensor):
#     def __init__(self, port='/dev/ttyAMA0', address=6, baudrate=4800,
#                  polling_rate=2, print_rate=5 * 60, debug=False, initial_delay=0,
#                  feed_names=["default_feed"], log_to_adafruit_flag=True,
#                  print_to_terminal_flag=True, lock=None, min_read_gap=0):
#         super().__init__(port, address, baudrate, polling_rate, print_rate,
#                          debug, initial_delay, feed_names, log_to_adafruit_flag,
#                          print_to_terminal_flag, lock, min_read_gap)
#         self.direction_map = {
#             0: "North",
#             45: "Northeast",
#             90: "East",
#             135: "Southeast",
#             180: "South",
#             225: "Southwest",
#             270: "West",
#             315: "Northwest"
#         }

#     def read(self):
#         try:
#             deg = self.instrument.read_register(0x0001, 0)
#             dir_str = self.direction_map.get(deg, "Unknown")
#             if self.debug:
#                 print(f"  [WindDirSensor] {deg}° → {dir_str}")
#             return [deg]  # If you also want to log the string, you'd need a separate feed.
#         except IOError as e:
#             print(f"Failed to read WindDirectionSensor: {e}")
#             return []


# class WindSpeedSensor(Sensor):
#     def read(self):
#         try:
#             speed = self.instrument.read_register(0x0000, 1)  # e.g., m/s or km/h
#             if self.debug:
#                 print(f"  [WindSpeedSensor] Speed={speed}")
#             return [speed]
#         except IOError as e:
#             print(f"Failed to read WindSpeedSensor: {e}")
#             return []


# class SoilMoistureSensor(Sensor):
#     def read(self):
#         """
#         Example registers for soil-moisture + soil-temperature.
#         Adjust REGISTER_MOISTURE and REGISTER_TEMPERATURE to your sensor's spec.
#         """
#         try:
#             REGISTER_MOISTURE = 0
#             REGISTER_TEMPERATURE = 1
#             moisture = self.instrument.read_register(REGISTER_MOISTURE, 1)      # e.g., %vol
#             temperature = self.instrument.read_register(REGISTER_TEMPERATURE, 1, True)  # e.g., tenths °C
#             if self.debug:
#                 print(f"  [SoilMoistureSensor] Moisture={moisture}%, Temp={temperature}°C")
#             return [moisture, temperature]
#         except IOError as e:
#             print(f"Failed to read SoilMoistureSensor: {e}")
#             return []


# class RainGaugeSensor:
#     GPIO_PIN = 17
#     DEBOUNCE_MS = 200
#     MM_PER_TIP = 0.5

#     def __init__(self,
#                  debug=False,
#                  feed_name="default_feed",
#                  log_to_adafruit_flag=True,
#                  print_to_terminal_flag=True,
#                  print_rate=5 * 60):
#         self.debug = debug
#         self.feed_name = feed_name
#         self.log_to_adafruit_flag = log_to_adafruit_flag
#         self.print_to_terminal_flag = print_to_terminal_flag
#         self.print_rate = print_rate

#         self.tip_count = 0
#         self._last_debounce = 0
#         self._count_lock = Lock()
#         self._current_day = datetime.date.today()
#         self._stop_event = Event()

#         GPIO.setmode(GPIO.BCM)
#         GPIO.setup(self.GPIO_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
#         GPIO.add_event_detect(
#             self.GPIO_PIN,
#             GPIO.FALLING,
#             callback=self._bucket_tipped,
#             bouncetime=self.DEBOUNCE_MS
#         )

#     def _bucket_tipped(self, channel):
#         now_ms = time.time() * 1000
#         with self._count_lock:
#             if now_ms - self._last_debounce >= self.DEBOUNCE_MS:
#                 self.tip_count += 1
#                 self._last_debounce = now_ms
#                 if self.debug:
#                     print(f"  [RainGauge] Tipped! Total tips today = {self.tip_count}")

#     def _daily_reset(self):
#         while not self._stop_event.is_set():
#             now = datetime.datetime.now()
#             next_midnight = (now + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
#             time_to_sleep = (next_midnight - now).total_seconds()
#             time.sleep(time_to_sleep)

#             with self._count_lock:
#                 self.tip_count = 0
#                 self._current_day = datetime.date.today()
#                 if self.debug:
#                     print("  [RainGauge] Tip count reset for new day")

#     def _log_and_print(self):
#         last_print_time = 0
#         while not self._stop_event.is_set():
#             now = time.time()
#             with self._count_lock:
#                 rainfall_mm = self.tip_count * self.MM_PER_TIP

#             if self.log_to_adafruit_flag:
#                 self.aio_client.send_data(self.feed_name, rainfall_mm)
#                 if self.debug:
#                     print(f"  [RainGauge] Logged daily rainfall {rainfall_mm} mm → '{self.feed_name}'")

#             if self.print_to_terminal_flag and now - last_print_time >= self.print_rate:
#                 print(f"RainGaugeSensor: {rainfall_mm:.1f} mm today")
#                 last_print_time = now

#             time.sleep(self.print_rate)

#     def start(self):
#         if self.debug:
#             print(f"Starting RainGaugeSensor with daily reset logic...")
#         self._stop_event.clear()
#         Thread(target=self._daily_reset, daemon=True).start()
#         Thread(target=self._log_and_print, daemon=True).start()

#     def stop(self):
#         if self.debug:
#             print("Stopping RainGaugeSensor...")
#         self._stop_event.set()
#         GPIO.cleanup(self.GPIO_PIN)


# class WeatherStation:
#     def __init__(self, aio_client, print_rate=5 * 60, print_to_terminal_flag=True):
#         self.sensors = {}
#         self.aio_client = aio_client
#         self.print_rate = print_rate
#         self.print_to_terminal_flag = print_to_terminal_flag

#     def add_sensor(self, name, sensor):
#         self.sensors[name] = sensor
#         setattr(sensor, 'aio_client', self.aio_client)

#     def start_all(self):
#         for name, sensor in self.sensors.items():
#             sensor.start()

#     def stop_all(self):
#         for sensor in self.sensors.values():
#             sensor.stop()



# # weather_station_library.py

# import minimalmodbus
# import time
# import datetime
# from threading import Thread, Event, Lock
# from Adafruit_IO import Data
# import RPi.GPIO as GPIO

# # ============================================================================
# # GENERIC MODBUS SENSOR CLASS
# # ============================================================================
# class ModbusSensor:
#     """A single, generic class for all Modbus sensors configured via dictionaries."""
#     def __init__(self, port, address, feed_names, metric_configs, polling_rate=60, debug=False, lock=None, **kwargs):
#         # Setup minimalmodbus instrument
#         self.instrument = minimalmodbus.Instrument(port, address)
#         for key, value in kwargs.items():
#             if key not in ['initial_delay', 'min_read_gap']: # Filter out non-serial kwargs
#                 setattr(self.instrument.serial, key, value)
#         self.instrument.mode = minimalmodbus.MODE_RTU

#         self.feed_names = feed_names
#         self.metric_configs = metric_configs
#         self.polling_rate = polling_rate
#         self.debug = debug
#         self.shared_port_lock = lock or Lock()
#         self.initial_delay = kwargs.get('initial_delay', 2)
#         self.min_read_gap = kwargs.get('min_read_gap', 2)
#         self.last_read_time = 0
        
#         self._stop_event = Event()
#         self.latest_values = None
#         self._value_lock = Lock()

#     def start(self):
#         if self.debug:
#             print(f"Starting poller for Modbus sensor (addr {self.instrument.address}) -> every {self.polling_rate}s.")
#         Thread(target=self._poll, daemon=True).start()

#     def stop(self):
#         self._stop_event.set()

#     def _apply_correction(self, raw_value, config):
#         """Applies calibration corrections based on the metric's config dictionary."""
#         if "correction" not in config or not config["correction"]:
#             return raw_value

#         corr_config = config["correction"]
#         corr_type = corr_config.get("type", "linear")

#         if corr_type == "linear":
#             offset = corr_config.get("offset", 0.0)
#             factor = corr_config.get("factor", 1.0)
#             corrected_value = (raw_value * factor) + offset
#             if self.debug: print(f"    Linear Correction: ({raw_value} * {factor}) + {offset} -> {corrected_value:.2f}")
#             return corrected_value

#         elif corr_type == "map":
#             raw_min = corr_config.get("raw_min", 0)
#             raw_max = corr_config.get("raw_max", 1023)
            
#             clamped_raw = max(raw_min, min(raw_value, raw_max))
#             if (raw_max - raw_min) == 0: return 50.0
            
#             percent = (clamped_raw - raw_min) * 100.0 / (raw_max - raw_min)
#             if self.debug: print(f"    Map Correction: {raw_value} -> {clamped_raw} -> {percent:.2f}%")
#             return percent

#         return raw_value

#     def _poll(self):
#         time.sleep(self.initial_delay)
#         while not self._stop_event.is_set():
#             now = time.time()
#             if now - self.last_read_time >= self.min_read_gap:
#                 values = []
#                 with self.shared_port_lock:
#                     self.last_read_time = now
#                     try:
#                         for metric, config in self.metric_configs.items():
#                             read_function_name = config.get("function", "read_register")
#                             read_function = getattr(self.instrument, read_function_name)
                            
#                             raw_value = read_function(
#                                 registeraddress=config["register"],
#                                 numberOfDecimals=config.get("decimals", 0),
#                                 signed=config.get("signed", False)
#                             )
                            
#                             corrected_value = self._apply_correction(raw_value, config)
#                             values.append(corrected_value)
                        
#                         if self.debug: print(f"  [Read OK] Addr {self.instrument.address}: Corrected values -> {values}")
#                         with self._value_lock:
#                             self.latest_values = values

#                     except (IOError, ValueError) as e:
#                         print(f"ERROR: Failed to read sensor at address {self.instrument.address}: {e}")
            
#             self._stop_event.wait(self.polling_rate)

#     def get_latest_value_and_feeds(self):
#         with self._value_lock:
#             if self.latest_values is None:
#                 return []
#             # Round values to 2 decimal places for clean logging
#             rounded_values = [round(v, 2) for v in self.latest_values]
#             return list(zip(self.feed_names, rounded_values))

# # ============================================================================
# # INTERRUPT-BASED SENSOR (Rain Gauge)
# # ============================================================================
# class RainGaugeSensor:
#     """A generic Rain Gauge class configured via parameters."""
#     def __init__(self, feed_name, gpio_pin, mm_per_tip, debounce_ms=250, debug=False):
#         self.feed_name = feed_name
#         self.gpio_pin = gpio_pin
#         self.mm_per_tip = mm_per_tip
#         self.debounce_ms = debounce_ms
#         self.debug = debug
        
#         self.tip_count_since_reset = 0
#         self._count_lock = Lock()
#         self._stop_event = Event()

#     def _bucket_tipped(self, channel):
#         with self._count_lock:
#             self.tip_count_since_reset += 1
#             if self.debug:
#                 print(f"  [Tipped!] Rain gauge on GPIO {self.gpio_pin}. Total today: {self.tip_count_since_reset}")

#     def start(self):
#         if self.debug: print(f"Starting RainGaugeSensor on GPIO {self.gpio_pin}...")
#         GPIO.setmode(GPIO.BCM)
#         GPIO.setup(self.gpio_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
#         GPIO.add_event_detect(self.gpio_pin, GPIO.FALLING, callback=self._bucket_tipped, bouncetime=self.debounce_ms)
#         Thread(target=self._daily_reset_thread, daemon=True).start()

#     def stop(self):
#         self._stop_event.set()
#         GPIO.cleanup(self.gpio_pin)

#     def _daily_reset_thread(self):
#         while not self._stop_event.is_set():
#             now = datetime.datetime.now()
#             next_midnight = (now + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=1, microsecond=0)
#             if self._stop_event.wait((next_midnight - now).total_seconds()):
#                 break
#             with self._count_lock:
#                 self.tip_count_since_reset = 0
#                 if self.debug: print(f"  [RainGauge] Daily tip count reset to 0 for GPIO {self.gpio_pin}.")

#     def get_latest_value_and_feeds(self):
#         with self._count_lock:
#             rainfall_mm = self.tip_count_since_reset * self.mm_per_tip
#         return [(self.feed_name, round(rainfall_mm, 2))]

# # ============================================================================
# # CENTRAL WEATHER STATION CONTROLLER
# # ============================================================================
# class WeatherStation:
#     """Orchestrates all sensors and handles data aggregation and uploading."""
#     def __init__(self, aio_client, upload_rate=300, print_rate=1200, **kwargs):
#         self.sensors = {}
#         self.aio_client = aio_client
#         self.upload_rate = upload_rate
#         self.print_rate = print_rate
#         self.print_to_terminal_flag = kwargs.get("print_to_terminal_flag", True)
#         self._stop_event = Event()

#     def add_sensor(self, name, sensor):
#         self.sensors[name] = sensor

#     def start_all(self):
#         print("Starting all sensor threads...")
#         for sensor in self.sensors.values():
#             sensor.start()
        
#         print(f"Starting central data uploader (uploads every {self.upload_rate}s)...")
#         Thread(target=self._data_aggregator_loop, daemon=True).start()

#     def stop_all(self):
#         self._stop_event.set()
#         for sensor in self.sensors.values():
#             sensor.stop()

#     def _data_aggregator_loop(self):
#         last_print_time = 0
#         self._stop_event.wait(10)

#         while not self._stop_event.is_set():
#             all_data_for_upload = []
#             all_data_for_print = {}

#             for name, sensor in self.sensors.items():
#                 sensor_data = sensor.get_latest_value_and_feeds()
#                 if sensor_data:
#                     all_data_for_upload.extend(sensor_data)
#                     all_data_for_print[name] = {item[0].split('.')[-1]: item[1] for item in sensor_data}

#             if all_data_for_upload:
#                 print(f"\n{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}: Aggregated data from {len(all_data_for_print)} sensor(s).")
#                 try:
#                     data_to_send = [Data(feed_id=item[0], value=item[1]) for item in all_data_for_upload]
#                     self.aio_client.send_batch_data(data_to_send)
#                     print("  → Batch data sent successfully to Adafruit IO.")
#                 except Exception as e:
#                     print(f"  → ERROR: Failed to send batch data: {e}")
            
#             if self.print_to_terminal_flag and (time.time() - last_print_time >= self.print_rate):
#                 print("\n--- Weather Station Status Summary ---")
#                 for name, data in sorted(all_data_for_print.items()):
#                     print(f"  {name:<15}: {data}")
#                 print("--------------------------------------\n")
#                 last_print_time = time.time()
            
#             self._stop_event.wait(self.upload_rate)

# In weather_station_library.py, replace the entire RainGaugeSensor class with this:

# weather_station_library.py

import os
import time
import datetime
import json
import sqlite3
from threading import Thread, Event, Lock
from Adafruit_IO import Data
import minimalmodbus
import pigpio

# ============================================================================
# DATA HANDLER PATTERN
# ============================================================================
class DataHandler:
    """A base class for any object that wants to receive data from the station."""
    def process(self, data_packet):
        raise NotImplementedError
    def start(self):
        pass
    def stop(self):
        pass

class AdafruitIOHandler(DataHandler):
    """This handler's job is to send data to Adafruit IO."""
    def __init__(self, aio_client, feed_prefix):
        self.aio_client, self.feed_prefix = aio_client, feed_prefix
    def process(self, data_packet):
        print(f"  [AdafruitIOHandler] Preparing batch upload...")
        data_to_send = []
        for sensor, metrics in data_packet.items():
            for metric, value in metrics.items():
                feed_id = f"{self.feed_prefix}.{sensor}-{metric}"
                data_to_send.append(Data(feed_id=feed_id, value=value))
        if data_to_send:
            try:
                self.aio_client.send_batch_data(data_to_send)
                print(f"  [AdafruitIOHandler]   → Batch data sent successfully.")
            except Exception as e:
                print(f"  [AdafruitIOHandler]   → ERROR: {e}")

class SQLiteHandler(DataHandler):
    """This handler's job is to save data to a local SQLite database."""
    def __init__(self, db_path):
        self.db_path, self.conn = db_path, None
    def start(self):
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.cursor().execute('''
            CREATE TABLE IF NOT EXISTS readings (
                timestamp TEXT NOT NULL, sensor TEXT NOT NULL,
                metric TEXT NOT NULL, value REAL NOT NULL,
                PRIMARY KEY (timestamp, sensor, metric))''')
        self.conn.commit()
        print(f"  [SQLiteHandler] Connected to database at {self.db_path}")
    def stop(self):
        if self.conn: self.conn.close(); print("  [SQLiteHandler] Database connection closed.")
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
    """This handler holds the latest data packet in memory for other apps."""
    def __init__(self):
        self._cache, self._lock = {}, Lock()
        print("  [DataCacheHandler] In-memory cache initialized.")
    def process(self, data_packet):
        with self._lock:
            self._cache['timestamp'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            self._cache['sensors'] = data_packet
        print(f"  [DataCacheHandler]   → Latest data cached.")
    def get_latest_data(self):
        with self._lock: return self._cache.copy()

# ============================================================================
# WEATHERSTATION CLASS (with config watcher)
# ============================================================================
class WeatherStation:
    """Orchestrates sensors and dispatches data to registered handlers."""
    def __init__(self, config_path='config.json'):
        self.sensors, self.handlers = {}, []
        self._stop_event = Event()
        self.config_path = config_path
        self.last_config_mtime = 0
        self.config = {}

    def add_sensor(self, name, sensor): self.sensors[name] = sensor
    def add_handler(self, handler): self.handlers.append(handler)

    def load_config(self):
        print("  [Config] Loading configuration...")
        with open(self.config_path, 'r') as f: self.config = json.load(f)
        self.last_config_mtime = os.path.getmtime(self.config_path)
        return self.config

    def start_all(self):
        print("\n--- Starting All Services ---")
        for handler in self.handlers: handler.start()
        for sensor in self.sensors.values(): sensor.start()
        Thread(target=self._data_dispatcher_loop, daemon=True).start()
        Thread(target=self._config_watcher_loop, daemon=True).start()

    def stop_all(self):
        self._stop_event.set()
        for sensor in self.sensors.values(): sensor.stop()
        for handler in self.handlers: handler.stop()

    def _data_dispatcher_loop(self):
        upload_rate = self.config.get('upload_rate', 300)
        self._stop_event.wait(10)
        while not self._stop_event.is_set():
            master_packet = {}
            for name, sensor in self.sensors.items():
                sensor_data_list = sensor.get_latest_value_and_feeds()
                if sensor_data_list:
                    if name == 'rain': metrics = {'total': sensor_data_list[0][1]}
                    else: metrics = {full_feed_name.split('-')[-1]: value for full_feed_name, value in sensor_data_list}
                    master_packet[name] = metrics
            
            if master_packet:
                print(f"\n{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}: Dispatching data...")
                for handler in self.handlers:
                    try: handler.process(master_packet)
                    except Exception as e: print(f"  → ERROR: Handler {type(handler).__name__} failed: {e}")
            
            # Use the latest upload_rate from the config
            upload_rate = self.config.get('upload_rate', 300)
            self._stop_event.wait(upload_rate)

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
        for sensor_obj in self.sensors.values():
            if hasattr(sensor_obj, 'polling_rate'):
                for conf in self.config['sensors'].values():
                    if conf['name'] == sensor_obj.name:
                        sensor_obj.polling_rate = conf['polling_rate']
                        sensor_obj.metric_configs = conf['metrics']
                        print(f"    → Updated settings for sensor '{sensor_obj.name}'")
                        break

# ============================================================================
# SENSOR CLASSES
# ============================================================================
class ModbusSensor:
    def __init__(self, name, port, address, feed_names, metric_configs, polling_rate, **kwargs):
        self.name, self.feed_names, self.metric_configs, self.polling_rate = name, feed_names, metric_configs, polling_rate
        self.instrument = minimalmodbus.Instrument(port, address)
        self.instrument.serial.baudrate = kwargs.get('baudrate', 4800)
        self.instrument.mode = minimalmodbus.MODE_RTU
        self.debug = kwargs.get('debug', False)
        self.shared_port_lock = kwargs.get('lock', Lock())
        self.initial_delay = kwargs.get('initial_delay', 2)
        self.min_read_gap = kwargs.get('min_read_gap', 2)
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
                        for metric, config in self.metric_configs.items():
                            read_function = getattr(self.instrument, config.get("function", "read_register"))
                            raw_value = read_function(
                                registeraddress=config["register"],
                                numberOfDecimals=config.get("decimals", 0),
                                signed=config.get("signed", False)
                            )
                            values.append(self._apply_correction(raw_value, config))
                        with self._value_lock: self.latest_values = values
                    except (IOError, ValueError) as e:
                        print(f"ERROR: Read failed for '{self.name}': {e}")
            self._stop_event.wait(self.polling_rate)

    def get_latest_value_and_feeds(self):
        with self._value_lock:
            if self.latest_values is None: return []
            return list(zip(self.feed_names, [round(v, 2) for v in self.latest_values]))

class RainGaugeSensor:
    """A Rain Gauge class using the robust pigpio library and daemon."""
    def __init__(self, name, feed_name, gpio_pin, mm_per_tip, **kwargs):
        self.name = name
        self.feed_name = feed_name
        self.gpio_pin = gpio_pin
        self.mm_per_tip = mm_per_tip
        self.debounce_us = kwargs.get('debounce_ms', 250) * 1000 # Convert ms to microseconds
        self.debug = kwargs.get('debug', False)

        self.tip_count = 0
        self._count_lock = Lock()
        self._stop_event = Event()

        self.pi = pigpio.pi() # Connects to the pigpio daemon
        self.callback_handler = None
        self._last_tick = 0

    def start(self):
        if self.debug: print(f"  Starting RainGauge on GPIO {self.gpio_pin} (using pigpio)...")

        if not self.pi.connected:
            print(f"  [RainGauge] ERROR: Could not connect to pigpio daemon. Is it running? Run 'sudo systemctl start pigpiod'")
            return

        # Set up the GPIO pin as an input with an internal pull-up resistor
        self.pi.set_mode(self.gpio_pin, pigpio.INPUT)
        self.pi.set_pull_up_down(self.gpio_pin, pigpio.PUD_UP)

        # Create the callback. The pigpio daemon will watch the pin and call our function when it changes.
        self.callback_handler = self.pi.callback(self.gpio_pin, pigpio.FALLING_EDGE, self._pi_callback)
        # Set the debounce period directly on the pin
        self.pi.set_glitch_filter(self.gpio_pin, self.debounce_us)


        # Start the thread that resets the count daily
        Thread(target=self._daily_reset_thread, daemon=True).start()

    def stop(self):
        if self.debug: print("  Stopping RainGaugeSensor...")
        self._stop_event.set()
        if self.callback_handler:
            self.callback_handler.cancel()  # Cleanly stop the callback
        if self.pi.connected:
            self.pi.stop()  # Disconnect from the pigpio daemon

    def _pi_callback(self, gpio, level, tick):
        """This function is called by the pigpio daemon on every tip."""
        # The glitch filter handles debouncing, so we just count the tip.
        with self._count_lock:
            self.tip_count += 1
            if self.debug:
                print(f"  [Tipped!] Rain gauge on GPIO {self.gpio_pin}. Total today: {self.tip_count}")

    def _daily_reset_thread(self):
        """This thread sleeps until midnight, then resets the daily tip count."""
        while not self._stop_event.is_set():
            now = datetime.datetime.now()
            next_midnight = (now + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=1, microsecond=0)
            
            # Use the event's wait method for a non-blocking sleep that can be interrupted
            if self._stop_event.wait((next_midnight - now).total_seconds()):
                # Exit if stop() was called during sleep
                break

            with self._count_lock:
                self.tip_count = 0
                if self.debug:
                    print(f"  [RainGauge] Daily tip count reset for GPIO {self.gpio_pin}.")

    def get_latest_value_and_feeds(self):
        """Provides the current data to the WeatherStation dispatcher."""
        with self._count_lock:
            # The metric name for the handler is 'total'
            return [(f"{self.feed_name}-total", round(self.tip_count * self.mm_per_tip, 2))]