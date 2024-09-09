# run_weather_station.py

from weather_station import WeatherStation, AtmosphericPressureSensor, AtmosphericTemperatureHumiditySensor, CO2Sensor, LightSensor, WindDirectionSensor, WindSpeedSensor
from Adafruit_IO import Client

# Adafruit IO credentials
x = 'x'
y = 'y'

# Create Adafruit IO client
aio = Client(x, y)
polling_rate = 1*60 # min to sectonds
initial_delay = 2

# Initialize Weather Station
weather_station = WeatherStation(aio)

# Define sensors with their respective feed names and logging flag
shared_port = '/dev/ttyAMA0'
sensors = [
    AtmosphericPressureSensor(port=shared_port, address=1, polling_rate=polling_rate, debug=True, initial_delay=initial_delay, feed_names=["tstfweatherstation.atmosphericpresuresensor-presure", "tstfweatherstation.atmosphericpresuresensor-temprature"], log_to_adafruit_flag=True),
    AtmosphericTemperatureHumiditySensor(port=shared_port, address=2, polling_rate=polling_rate, debug=True, initial_delay=initial_delay*2, feed_names=["tstfweatherstation.atmospherictemphumi-humidity", "tstfweatherstation.atmospherictemphumi-temprature"], log_to_adafruit_flag=True),
    CO2Sensor(port=shared_port, address=3, polling_rate=polling_rate, debug=True, initial_delay=initial_delay*3, feed_names=["tstfweatherstation.co2-co2transmitter"], log_to_adafruit_flag=True),
    LightSensor(port='/dev/ttyAMA0', address=4, polling_rate=polling_rate, debug=True, initial_delay=initial_delay*4, feed_names=["tstfweatherstation.light-lightintensitytransmitter"], log_to_adafruit_flag=True),
    WindDirectionSensor(port='/dev/ttyAMA0', address=6, polling_rate=polling_rate, debug=True, initial_delay=initial_delay*5, feed_names=["tstfweatherstation.winddirection"], log_to_adafruit_flag=True),
    WindSpeedSensor(port='/dev/ttyAMA0', address=7, polling_rate=polling_rate, debug=True, initial_delay=initial_delay*6, feed_names=["tstfweatherstation.windspeed"], log_to_adafruit_flag=True),
]

# Add sensors to the weather station
for i, sensor in enumerate(sensors):
    weather_station.add_sensor(f"sensor_{i+1}", sensor)

# Add other sensors that may use different ports
weather_station.add_sensor("light", LightSensor(port='/dev/ttyAMA0', address=4, polling_rate=polling_rate, debug=True, initial_delay=initial_delay*4, feed_names=["tstfweatherstation.light-lightintensitytransmitter"], log_to_adafruit_flag=True))
weather_station.add_sensor("wind_direction", WindDirectionSensor(port='/dev/ttyAMA0', address=6, polling_rate=polling_rate, debug=True, initial_delay=initial_delay*5, feed_names=["tstfweatherstation.winddirection"], log_to_adafruit_flag=True))
weather_station.add_sensor("wind_speed", WindSpeedSensor(port='/dev/ttyAMA0', address=7, polling_rate=polling_rate, debug=True, initial_delay=initial_delay*6, feed_names=["tstfweatherstation.windspeed"], log_to_adafruit_flag=True))

# Start all sensors
weather_station.start_all()
