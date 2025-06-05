# # #run_weather_station.py
# from weather_station import WeatherStation, AtmosphericPressureSensor, AtmosphericTemperatureHumiditySensor, CO2Sensor, LightSensor, WindDirectionSensor, WindSpeedSensor
# from Adafruit_IO import Client
# from threading import Lock
# import minimalmodbus
# import time

# # Adafruit IO credentials


# # Create Adafruit IO client
# aio = Client(ADAFRUIT_IO_USERNAME, ADAFRUIT_IO_KEY)
# polling_rate = 60 * 60  # Polling rate for sending data (in min)
# print_rate = 20 * 60  # Rate for printing to the terminal (in min)
# initial_delay = 4
# min_read_gap = 4  # Ensure at least 2 seconds between reads from different sensors
# print_to_terminal_flag = True  # Set this to False if you want to disable printing

# # Shared lock for sensors on the same port
# shared_port_lock = Lock()

# # Initialize Weather Station
# weather_station = WeatherStation(aio, print_rate=print_rate, print_to_terminal_flag=print_to_terminal_flag)

# # List of serial ports to test
# ports = ['/dev/ttyACM0', '/dev/ttyACM1', '/dev/ttyACM2', '/dev/ttyACM3']
# sensor_addresses = [1, 2, 3, 4, 5, 6, 7]
# baudrate = 4800  # Assumed baudrate for your setup
# timeout = 2  # Timeout for serial connection

# def test_sensor(port, address):
#     try:
#         # Create instrument
#         instrument = minimalmodbus.Instrument(port, address)
#         instrument.serial.baudrate = baudrate
#         instrument.serial.timeout = timeout
        
#         # Determine register to read based on address
#         if address in [5, 2, 7]:
#             register = 0
#             decimal_places = 1
#         elif address == 3:
#             register = 1  # Adjusted to correct register for CO2 sensor
#             decimal_places = 0
#         elif address in [4, 6]:
#             register = 0
#             decimal_places = 0
#         else:
#             print(f"Unknown sensor address: {address}")
#             return None
            
#         # Attempt to read the specified register
#         response = instrument.read_register(register, decimal_places)
#         print(f"Sensor at address {address} on {port} responded with data: {response}")
#         return response
#     except IOError:
#         print(f"No response from sensor at address {address} on {port}")
#         return None

# # Discover sensors
# found_sensors = {}
# for port in ports:
#     for address in sensor_addresses:
#         print(f"Testing port {port} with address {address}...")
#         response = test_sensor(port, address)
#         if response is not None:
#             found_sensors[address] = port  # Store response with port in the dictionary
#             print(f"Found sensor at address {address} on port {port} with data: {response}")
#         time.sleep(2)  # Small delay between tests

# # Initialize sensors based on discovered addresses
# sensors = []
# for address, port in found_sensors.items():
#     if address == 1:
#         sensors.append(AtmosphericPressureSensor(port=port, address=address, polling_rate=polling_rate, debug=True, initial_delay=initial_delay,
#                                                   feed_names=["tstfweatherstation.atmosphericpressuresensor-pressure", "tstfweatherstation.atmosphericpressuresensor-temperature"],
#                                                   log_to_adafruit_flag=True, print_to_terminal_flag=print_to_terminal_flag, lock=shared_port_lock, min_read_gap=min_read_gap))
#     elif address == 2:
#         sensors.append(AtmosphericTemperatureHumiditySensor(port=port, address=address, polling_rate=polling_rate, debug=True, initial_delay=initial_delay,
#                                                            feed_names=["tstfweatherstation.atmospherictemphumi-humidity", "tstfweatherstation.atmospherictemphumi-temperature"],
#                                                            log_to_adafruit_flag=True, print_to_terminal_flag=print_to_terminal_flag, lock=shared_port_lock, min_read_gap=min_read_gap))
#     elif address == 3:
#         sensors.append(CO2Sensor(port=port, address=address, polling_rate=polling_rate, debug=True, initial_delay=initial_delay,
#                                   feed_names=["tstfweatherstation.co2-co2transmitter"],
#                                   log_to_adafruit_flag=True, print_to_terminal_flag=print_to_terminal_flag, lock=shared_port_lock, min_read_gap=min_read_gap))
#     elif address == 4:
#         sensors.append(LightSensor(port=port, address=address, polling_rate=polling_rate, debug=True, initial_delay=initial_delay,
#                                    feed_names=["tstfweatherstation.light-lightintensitytransmitter"],
#                                    log_to_adafruit_flag=True, print_to_terminal_flag=print_to_terminal_flag, lock=shared_port_lock, min_read_gap=min_read_gap))
#     elif address == 5:
#         sensors.append(AtmosphericPressureSensor(port=port, address=address, polling_rate=polling_rate, debug=True, initial_delay=initial_delay,
#                                                   feed_names=["tstfweatherstation.atmosphericpressuresensor-pressure", "tstfweatherstation.atmosphericpressuresensor-temperature"],
#                                                   log_to_adafruit_flag=True, print_to_terminal_flag=print_to_terminal_flag, lock=shared_port_lock, min_read_gap=min_read_gap))
#     elif address == 6:
#         sensors.append(WindDirectionSensor(port=port, address=address, polling_rate=polling_rate, debug=True, initial_delay=initial_delay,
#                                            feed_names=["tstfweatherstation.winddirection"],
#                                            log_to_adafruit_flag=True, print_to_terminal_flag=print_to_terminal_flag, lock=shared_port_lock, min_read_gap=min_read_gap))
#     elif address == 7:
#         sensors.append(WindSpeedSensor(port=port, address=address, polling_rate=polling_rate, debug=True, initial_delay=initial_delay,
#                                        feed_names=["tstfweatherstation.windspeed"],
#                                        log_to_adafruit_flag=True, print_to_terminal_flag=print_to_terminal_flag, lock=shared_port_lock, min_read_gap=min_read_gap))

# # Add sensors to the weather station
# for i, sensor in enumerate(sensors):
#     weather_station.add_sensor(f"sensor_{i+1}", sensor)

# # Start all sensors
# weather_station.start_all()





# run_weather_station.py (UPDATED for interrupt-only rain gauge)

from weather_station import (
    WeatherStation,
    AtmosphericPressureSensor,
    AtmosphericTemperatureHumiditySensor,
    CO2Sensor,
    LightSensor,
    WindDirectionSensor,
    WindSpeedSensor,
    SoilMoistureSensor,
    RainGaugeSensor,
)
from Adafruit_IO import Client
from threading import Lock
import minimalmodbus
import time

ADAFRUIT_IO_USERNAME = "YOUR_USERNAME"
ADAFRUIT_IO_KEY = "YOUR_KEY"

aio = Client(ADAFRUIT_IO_USERNAME, ADAFRUIT_IO_KEY)

polling_rate = 60 * 60        # for Modbus sensors
print_rate = 20 * 60
initial_delay = 4
min_read_gap = 2

shared_port_lock = Lock()

weather_station = WeatherStation(
    aio_client=aio,
    print_rate=print_rate,
    print_to_terminal_flag=True
)

ports = ['/dev/ttyACM0', '/dev/ttyACM1', '/dev/ttyACM2', '/dev/ttyACM3']
sensor_addresses = [1, 2, 3, 4, 5, 6, 7]
baudrate = 4800
timeout = 2

def test_sensor(port, address):
    try:
        inst = minimalmodbus.Instrument(port, address)
        inst.serial.baudrate = baudrate
        inst.serial.bytesize = 8
        inst.serial.parity = minimalmodbus.serial.PARITY_NONE
        inst.serial.stopbits = 1
        inst.serial.timeout = timeout
        inst.mode = minimalmodbus.MODE_RTU
        _ = inst.read_register(0, 0)
        return True
    except (IOError, ValueError):
        return False

found_sensors = {}
for port in ports:
    for addr in sensor_addresses:
        print(f"Testing port {port}, address {addr}...")
        if test_sensor(port, addr):
            print(f"  → Sensor found at address {addr} on {port}")
            found_sensors[addr] = port
        time.sleep(1)

for addr, port in found_sensors.items():
    if addr == 1:
        soil = SoilMoistureSensor(
            port=port,
            address=addr,
            polling_rate=polling_rate,
            print_rate=print_rate,
            debug=True,
            initial_delay=initial_delay,
            feed_names=[
                "tstfweatherstation.soilmoisture-moisture",
                "tstfweatherstation.soilmoisture-temperature"
            ],
            log_to_adafruit_flag=True,
            print_to_terminal_flag=True,
            lock=shared_port_lock,
            min_read_gap=min_read_gap
        )
        weather_station.add_sensor("soil_moisture", soil)

    elif addr == 2:
        atm_th = AtmosphericTemperatureHumiditySensor(
            port=port,
            address=addr,
            polling_rate=polling_rate,
            print_rate=print_rate,
            debug=True,
            initial_delay=initial_delay,
            feed_names=[
                "tstfweatherstation.atm_th-humidity",
                "tstfweatherstation.atm_th-temperature"
            ],
            log_to_adafruit_flag=True,
            print_to_terminal_flag=True,
            lock=shared_port_lock,
            min_read_gap=min_read_gap
        )
        weather_station.add_sensor("atm_temp_humi", atm_th)

    elif addr == 3:
        co2 = CO2Sensor(
            port=port,
            address=addr,
            polling_rate=polling_rate,
            print_rate=print_rate,
            debug=True,
            initial_delay=initial_delay,
            feed_names=["tstfweatherstation.co2-co2transmitter"],
            log_to_adafruit_flag=True,
            print_to_terminal_flag=True,
            lock=shared_port_lock,
            min_read_gap=min_read_gap
        )
        weather_station.add_sensor("co2_sensor", co2)

    elif addr == 4:
        light = LightSensor(
            port=port,
            address=addr,
            polling_rate=polling_rate,
            print_rate=print_rate,
            debug=True,
            initial_delay=initial_delay,
            feed_names=["tstfweatherstation.light-lightintensity"],
            log_to_adafruit_flag=True,
            print_to_terminal_flag=True,
            lock=shared_port_lock,
            min_read_gap=min_read_gap
        )
        weather_station.add_sensor("light_sensor", light)

    elif addr == 5:
        press = AtmosphericPressureSensor(
            port=port,
            address=addr,
            polling_rate=polling_rate,
            print_rate=print_rate,
            debug=True,
            initial_delay=initial_delay,
            feed_names=[
                "tstfweatherstation.atm_pressure-pressure",
                "tstfweatherstation.atm_pressure-temperature"
            ],
            log_to_adafruit_flag=True,
            print_to_terminal_flag=True,
            lock=shared_port_lock,
            min_read_gap=min_read_gap
        )
        weather_station.add_sensor("atm_pressure", press)

    elif addr == 6:
        wind_dir = WindDirectionSensor(
            port=port,
            address=addr,
            polling_rate=polling_rate,
            print_rate=print_rate,
            debug=True,
            initial_delay=initial_delay,
            feed_names=["tstfweatherstation.winddirection"],
            log_to_adafruit_flag=True,
            print_to_terminal_flag=True,
            lock=shared_port_lock,
            min_read_gap=min_read_gap
        )
        weather_station.add_sensor("wind_direction", wind_dir)

    elif addr == 7:
        wind_spd = WindSpeedSensor(
            port=port,
            address=addr,
            polling_rate=polling_rate,
            print_rate=print_rate,
            debug=True,
            initial_delay=initial_delay,
            feed_names=["tstfweatherstation.windspeed"],
            log_to_adafruit_flag=True,
            print_to_terminal_flag=True,
            lock=shared_port_lock,
            min_read_gap=min_read_gap
        )
        weather_station.add_sensor("wind_speed", wind_spd)

# RainGaugeSensor (interrupt-driven, no polling_rate needed)
rain_sensor = RainGaugeSensor(
    debug=True,
    feed_name="tstfweatherstation.raingauge",
    log_to_adafruit_flag=True,
    print_to_terminal_flag=True,
    print_rate=print_rate
)
weather_station.add_sensor("rain_gauge", rain_sensor)

weather_station.start_all()
# You can stop it with: weather_station.stop_all()

