# weather_station.py

import minimalmodbus
import time
from threading import Thread, Event

class Sensor:
    def __init__(self, port='/dev/ttyAMA0', address=1, baudrate=4800, polling_rate=2, debug=False, initial_delay=0):
        self.instrument = minimalmodbus.Instrument(port, address)
        self.instrument.serial.baudrate = baudrate
        self.instrument.serial.bytesize = 8
        self.instrument.serial.parity = minimalmodbus.serial.PARITY_NONE
        self.instrument.serial.stopbits = 1
        self.instrument.serial.timeout = 2  # Increase timeout to 2 seconds
        self.polling_rate = polling_rate
        self.debug = debug
        self.initial_delay = initial_delay
        self.active = False
        self._stop_event = Event()

    def start(self):
        if self.debug:
            print(f"Starting {self.__class__.__name__} sensor polling with initial delay of {self.initial_delay} seconds.")
        self.active = True
        self._stop_event.clear()
        Thread(target=self._poll).start()

    def stop(self):
        if self.debug:
            print(f"Stopping {self.__class__.__name__} sensor polling.")
        self.active = False
        self._stop_event.set()

    def _poll(self):
        time.sleep(self.initial_delay)  # Initial delay to stagger polling
        while not self._stop_event.is_set():
            self.read()
            time.sleep(self.polling_rate)

    def read(self):
        raise NotImplementedError("This method should be implemented by subclasses")

class AtmosphericPressureSensor(Sensor):
    def read(self):
        try:
            pressure = self.instrument.read_register(0x0000, 1)
            temperature = self.instrument.read_register(0x0001, 1, signed=True)
            if self.debug:
                print(f"Atmospheric Pressure: {pressure} Kpa, Temperature: {temperature} °C")
            return {"pressure": pressure, "temperature": temperature}
        except IOError as e:
            print(f"Failed to read from AtmosphericPressureSensor: {e}")

class AtmosphericTemperatureHumiditySensor(Sensor):
    def read(self):
        try:
            humidity = self.instrument.read_register(0x0000, 1)
            temperature = self.instrument.read_register(0x0001, 1, signed=True)
            if self.debug:
                print(f"Humidity: {humidity} %RH, Temperature: {temperature} °C")
            return {"humidity": humidity, "temperature": temperature}
        except IOError as e:
            print(f"Failed to read from AtmosphericTemperatureHumiditySensor: {e}")

class CO2Sensor(Sensor):
    def read(self):
        try:
            co2_concentration = self.instrument.read_register(0x0002, 0)
            if self.debug:
                print(f"CO2 Concentration: {co2_concentration} ppm")
            return {"co2_concentration": co2_concentration}
        except IOError as e:
            print(f"Failed to read from CO2Sensor: {e}")

class LightSensor(Sensor):
    def read(self):
        try:
            light_intensity = self.instrument.read_register(0x0006, 0)
            if self.debug:
                print(f"Light Intensity: {light_intensity} Lux")
            return {"light_intensity": light_intensity}
        except IOError as e:
            print(f"Failed to read from LightSensor: {e}")

class WindDirectionSensor(Sensor):
    def __init__(self, port='/dev/ttyACM0', address=6, baudrate=4800, polling_rate=2, debug=False, initial_delay=0):
        super().__init__(port, address, baudrate, polling_rate, debug, initial_delay)
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
            wind_direction_degrees = self.instrument.read_register(0x0001, 0)
            wind_direction = self.direction_map.get(wind_direction_degrees, "Unknown Direction")
            if self.debug:
                print(f"Wind Direction: {wind_direction_degrees}° ({wind_direction})")
            return {"wind_direction_degrees": wind_direction_degrees, "wind_direction": wind_direction}
        except IOError as e:
            print(f"Failed to read from WindDirectionSensor: {e}")

class WindSpeedSensor(Sensor):
    def read(self):
        try:
            wind_speed = self.instrument.read_register(0x0000, 1)
            if self.debug:
                print(f"Wind Speed: {wind_speed} m/s")
            return {"wind_speed": wind_speed}
        except IOError as e:
            print(f"Failed to read from WindSpeedSensor: {e}")

class WeatherStation:
    def __init__(self):
        self.sensors = {}

    def add_sensor(self, name, sensor):
        self.sensors[name] = sensor

    def start_sensor(self, name):
        if name in self.sensors:
            self.sensors[name].start()

    def stop_sensor(self, name):
        if name in self.sensors:
            self.sensors[name].stop()

    def set_polling_rate(self, name, polling_rate):
        if name in self.sensors:
            self.sensors[name].polling_rate = polling_rate

    def set_debug_mode(self, name, debug):
        if name in self.sensors:
            self.sensors[name].debug = debug

    def start_all(self):
        for sensor in self.sensors.values():
            sensor.start()

    def stop_all(self):
        for sensor in self.sensors.values():
            sensor.stop()
