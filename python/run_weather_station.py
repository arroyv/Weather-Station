# run_weather_station.py

from weather_station import WeatherStation, AtmosphericPressureSensor, AtmosphericTemperatureHumiditySensor, CO2Sensor, LightSensor, WindDirectionSensor, WindSpeedSensor

# Initialize Weather Station
weather_station = WeatherStation()

# Define sensors sharing the same port
shared_port = '/dev/ttyAMA0'
sensors = [
    AtmosphericPressureSensor(port=shared_port, address=1, polling_rate=6, debug=True, initial_delay=0),
    AtmosphericTemperatureHumiditySensor(port=shared_port, address=2, polling_rate=6, debug=True, initial_delay=2),
    CO2Sensor(port=shared_port, address=3, polling_rate=6, debug=True, initial_delay=4),
]

# Add sensors to the weather station
for i, sensor in enumerate(sensors):
    weather_station.add_sensor(f"sensor_{i+1}", sensor)

# Add other sensors that may use different ports
weather_station.add_sensor("light", LightSensor(port='/dev/ttyAMA0', address=4, polling_rate=6, debug=True, initial_delay=6))
weather_station.add_sensor("wind_direction", WindDirectionSensor(port='/dev/ttyAMA0', address=6, polling_rate=6, debug=True, initial_delay=8))
weather_station.add_sensor("wind_speed", WindSpeedSensor(port='/dev/ttyAMA0', address=7, polling_rate=8, debug=True, initial_delay=10))

# Start all sensors
weather_station.start_all()

# Example: Stop all sensors after some time
import time
time.sleep(40)  # Let sensors run for 20 seconds
weather_station.stop_all()
