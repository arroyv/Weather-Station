#weather_station.py
import minimalmodbus
import time
from threading import Thread, Event, Lock
from Adafruit_IO import Client

class Sensor:
    def __init__(self, port='/dev/ttyAMA0', address=1, baudrate=4800, polling_rate=2, print_rate=5*60, debug=False, initial_delay=0, feed_names=["default_feed"], log_to_adafruit_flag=True, print_to_terminal_flag=True, lock=None, min_read_gap=0):
        self.instrument = minimalmodbus.Instrument(port, address)
        self.instrument.serial.baudrate = baudrate
        self.instrument.serial.bytesize = 8
        self.instrument.serial.parity = minimalmodbus.serial.PARITY_NONE
        self.instrument.serial.stopbits = 1
        self.instrument.serial.timeout = 3  # Increase timeout to 2 seconds
        self.polling_rate = polling_rate  # Rate for sending data to Adafruit IO
        self.print_rate = print_rate  # Rate for printing to the terminal
        self.debug = debug
        self.initial_delay = initial_delay
        self.feed_names = feed_names  # List of feed names to log data to
        self.log_to_adafruit_flag = log_to_adafruit_flag  # Flag to control logging
        self.print_to_terminal_flag = print_to_terminal_flag  # Flag to control printing to terminal
        self.active = False
        self._stop_event = Event()
        self.lock = lock  # Shared lock for port synchronization
        self.min_read_gap = min_read_gap  # Minimum gap between consecutive reads
        self.last_read_time = 0  # Track the last time the sensor was read

    def start(self):
        if self.debug:
            print(f"Starting {self.__class__.__name__} sensor polling after {self.initial_delay} seconds.")
        self.active = True
        self._stop_event.clear()
        Thread(target=self._poll).start()

    def stop(self):
        if self.debug:
            print(f"Stopping {self.__class__.__name__} sensor polling.")
        self.active = False
        self._stop_event.set()

    def _poll(self):
        time.sleep(self.initial_delay)  # Apply initial delay before the first read
        last_print_time = 0  # Track last time data was printed
        last_log_time = 0  # Track last time data was logged to Adafruit IO

        while not self._stop_event.is_set():
            current_time = time.time()

            # Ensure minimum time gap between reads to prevent overlap
            if current_time - self.last_read_time >= self.min_read_gap:
                # Acquire the lock before reading the sensor
                with self.lock:
                    data = self.read()  # Data is a list of numeric values
                    self.last_read_time = current_time  # Update the last read time

                    # Log data to Adafruit IO based on polling_rate
                    if data and self.log_to_adafruit_flag and current_time - last_log_time >= self.polling_rate:
                        self.log_to_adafruit(data)
                        last_log_time = current_time

                    # Print data to terminal based on print_rate if flag is enabled
                    if current_time - last_print_time >= self.print_rate and data and self.print_to_terminal_flag:
                        self.print_to_terminal(data)
                        last_print_time = current_time

            time.sleep(1)  # Sleep briefly to avoid hogging the CPU

    def log_to_adafruit(self, data):
        # Log each value to its respective feed
        for value, feed_name in zip(data, self.feed_names):
            self.log_data(feed_name, value)

    def print_to_terminal(self, data):
        # Print data to the terminal
        print(f"Sensor {self.__class__.__name__}: {data}")

    def read(self):
        raise NotImplementedError("This method should be implemented by subclasses")

    def log_data(self, feed_name, value):
        # Log numeric values to Adafruit IO feed
        self.aio_client.send_data(feed_name, value)
        print(f"Logged value {value} to feed {feed_name}")

class AtmosphericPressureSensor(Sensor):
    def read(self):
        try:
            pressure = self.instrument.read_register(0x0000, 1)  # Numeric value
            temperature = self.instrument.read_register(0x0001, 1, signed=True)  # Numeric value
            if self.debug:
                print(f"Pressure: {pressure}, Temperature: {temperature}")
            return [pressure, temperature]  # Return as a list of numeric values
        except IOError as e:
            print(f"Failed to read from AtmosphericPressureSensor: {e}")
            return []

class AtmosphericTemperatureHumiditySensor(Sensor):
    def read(self):
        try:
            humidity = self.instrument.read_register(0x0000, 1)  # Numeric value
            temperature = self.instrument.read_register(0x0001, 1, signed=True)  # Numeric value
            if self.debug:
                print(f"Humidity: {humidity}, Temperature: {temperature}")
            return [humidity, temperature]  # Return as a list of numeric values
        except IOError as e:
            print(f"Failed to read from AtmosphericTemperatureHumiditySensor: {e}")
            return []

class CO2Sensor(Sensor):
    def read(self):
        try:
            co2_concentration = self.instrument.read_register(0x0002, 0)  # Numeric value
            if self.debug:
                print(f"CO2 Concentration: {co2_concentration}")
            return [co2_concentration]  # Return as a list with one numeric value
        except IOError as e:
            print(f"Failed to read from CO2Sensor: {e}")
            return []

class LightSensor(Sensor):
    def read(self):
        try:
            light_intensity = self.instrument.read_register(0x0006, 0)  # Numeric value
            if self.debug:
                print(f"Light Intensity: {light_intensity}")
            return [light_intensity]  # Return as a list with one numeric value
        except IOError as e:
            print(f"Failed to read from LightSensor: {e}")
            return []

class WindDirectionSensor(Sensor):
    def __init__(self, port='/dev/ttyAMA0', address=6, baudrate=4800, polling_rate=2, print_rate=5*60, debug=False, initial_delay=0, feed_names=["default_feed"], log_to_adafruit_flag=True, print_to_terminal_flag=True, lock=None, min_read_gap=0):
        super().__init__(port, address, baudrate, polling_rate, print_rate, debug, initial_delay, feed_names, log_to_adafruit_flag, print_to_terminal_flag, lock, min_read_gap)
        self.direction_map = {
            0: "North",
            45: "Northeast",
            90: "East",
            135: "Southeast",
            180: "South",
            225: "Southwest",
            270: "West",
            315: "Northwest"
        }

    def read(self):
        try:
            wind_direction_degrees = self.instrument.read_register(0x0001, 0)  # Numeric value
            direction = self.direction_map.get(wind_direction_degrees, "Unknown Direction")
            if self.debug:
                print(f"Wind Direction: {wind_direction_degrees} ({direction})")
            return [wind_direction_degrees]  # Return as a list with one numeric value
        except IOError as e:
            print(f"Failed to read from WindDirectionSensor: {e}")
            return []

class WindSpeedSensor(Sensor):
    def read(self):
        try:
            wind_speed = self.instrument.read_register(0x0000, 1)  # Numeric value
            if self.debug:
                print(f"Wind Speed: {wind_speed}")
            return [wind_speed]  # Return as a list with one numeric value
        except IOError as e:
            print(f"Failed to read from WindSpeedSensor: {e}")
            return []

class WeatherStation:
    def __init__(self, aio_client, print_rate=5*60, print_to_terminal_flag=True):
        self.sensors = {}
        self.aio_client = aio_client
        self.print_rate = print_rate  # Rate for printing to the terminal
        self.print_to_terminal_flag = print_to_terminal_flag  # Flag to control terminal printing

    def add_sensor(self, name, sensor):
        self.sensors[name] = sensor
        sensor.aio_client = self.aio_client  # Pass the Adafruit IO client to each sensor

    def start_all(self):
        for sensor_name, sensor in self.sensors.items():
            # Start each sensor with its own polling rate and initial delay
            sensor.start()

    def stop_all(self):
        for sensor in self.sensors.values():
            sensor.stop()


