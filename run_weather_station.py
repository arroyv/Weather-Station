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





# # run_weather_station.py (UPDATED for interrupt-only rain gauge)

# from weather_station import (
#     WeatherStation,
#     AtmosphericPressureSensor,
#     AtmosphericTemperatureHumiditySensor,
#     CO2Sensor,
#     LightSensor,
#     WindDirectionSensor,
#     WindSpeedSensor,
#     SoilMoistureSensor,
#     RainGaugeSensor,
# )
# from Adafruit_IO import Client
# from threading import Lock
# import minimalmodbus
# import time

# ADAFRUIT_IO_USERNAME = "YOUR_USERNAME"
# ADAFRUIT_IO_KEY = "YOUR_KEY"

# aio = Client(ADAFRUIT_IO_USERNAME, ADAFRUIT_IO_KEY)

# polling_rate = 60 * 60        # for Modbus sensors
# print_rate = 20 * 60
# initial_delay = 4
# min_read_gap = 2

# shared_port_lock = Lock()

# weather_station = WeatherStation(
#     aio_client=aio,
#     print_rate=print_rate,
#     print_to_terminal_flag=True
# )

# ports = ['/dev/ttyACM0', '/dev/ttyACM1', '/dev/ttyACM2', '/dev/ttyACM3']
# sensor_addresses = [1, 2, 3, 4, 5, 6, 7]
# baudrate = 4800
# timeout = 2

# def test_sensor(port, address):
#     try:
#         inst = minimalmodbus.Instrument(port, address)
#         inst.serial.baudrate = baudrate
#         inst.serial.bytesize = 8
#         inst.serial.parity = minimalmodbus.serial.PARITY_NONE
#         inst.serial.stopbits = 1
#         inst.serial.timeout = timeout
#         inst.mode = minimalmodbus.MODE_RTU
#         _ = inst.read_register(0, 0)
#         return True
#     except (IOError, ValueError):
#         return False

# found_sensors = {}
# for port in ports:
#     for addr in sensor_addresses:
#         print(f"Testing port {port}, address {addr}...")
#         if test_sensor(port, addr):
#             print(f"  → Sensor found at address {addr} on {port}")
#             found_sensors[addr] = port
#         time.sleep(1)

# for addr, port in found_sensors.items():
#     if addr == 1:
#         soil = SoilMoistureSensor(
#             port=port,
#             address=addr,
#             polling_rate=polling_rate,
#             print_rate=print_rate,
#             debug=True,
#             initial_delay=initial_delay,
#             feed_names=[
#                 "tstfweatherstation.soilmoisture-moisture",
#                 "tstfweatherstation.soilmoisture-temperature"
#             ],
#             log_to_adafruit_flag=True,
#             print_to_terminal_flag=True,
#             lock=shared_port_lock,
#             min_read_gap=min_read_gap
#         )
#         weather_station.add_sensor("soil_moisture", soil)

#     elif addr == 2:
#         atm_th = AtmosphericTemperatureHumiditySensor(
#             port=port,
#             address=addr,
#             polling_rate=polling_rate,
#             print_rate=print_rate,
#             debug=True,
#             initial_delay=initial_delay,
#             feed_names=[
#                 "tstfweatherstation.atm_th-humidity",
#                 "tstfweatherstation.atm_th-temperature"
#             ],
#             log_to_adafruit_flag=True,
#             print_to_terminal_flag=True,
#             lock=shared_port_lock,
#             min_read_gap=min_read_gap
#         )
#         weather_station.add_sensor("atm_temp_humi", atm_th)

#     elif addr == 3:
#         co2 = CO2Sensor(
#             port=port,
#             address=addr,
#             polling_rate=polling_rate,
#             print_rate=print_rate,
#             debug=True,
#             initial_delay=initial_delay,
#             feed_names=["tstfweatherstation.co2-co2transmitter"],
#             log_to_adafruit_flag=True,
#             print_to_terminal_flag=True,
#             lock=shared_port_lock,
#             min_read_gap=min_read_gap
#         )
#         weather_station.add_sensor("co2_sensor", co2)

#     elif addr == 4:
#         light = LightSensor(
#             port=port,
#             address=addr,
#             polling_rate=polling_rate,
#             print_rate=print_rate,
#             debug=True,
#             initial_delay=initial_delay,
#             feed_names=["tstfweatherstation.light-lightintensity"],
#             log_to_adafruit_flag=True,
#             print_to_terminal_flag=True,
#             lock=shared_port_lock,
#             min_read_gap=min_read_gap
#         )
#         weather_station.add_sensor("light_sensor", light)

#     elif addr == 5:
#         press = AtmosphericPressureSensor(
#             port=port,
#             address=addr,
#             polling_rate=polling_rate,
#             print_rate=print_rate,
#             debug=True,
#             initial_delay=initial_delay,
#             feed_names=[
#                 "tstfweatherstation.atm_pressure-pressure",
#                 "tstfweatherstation.atm_pressure-temperature"
#             ],
#             log_to_adafruit_flag=True,
#             print_to_terminal_flag=True,
#             lock=shared_port_lock,
#             min_read_gap=min_read_gap
#         )
#         weather_station.add_sensor("atm_pressure", press)

#     elif addr == 6:
#         wind_dir = WindDirectionSensor(
#             port=port,
#             address=addr,
#             polling_rate=polling_rate,
#             print_rate=print_rate,
#             debug=True,
#             initial_delay=initial_delay,
#             feed_names=["tstfweatherstation.winddirection"],
#             log_to_adafruit_flag=True,
#             print_to_terminal_flag=True,
#             lock=shared_port_lock,
#             min_read_gap=min_read_gap
#         )
#         weather_station.add_sensor("wind_direction", wind_dir)

#     elif addr == 7:
#         wind_spd = WindSpeedSensor(
#             port=port,
#             address=addr,
#             polling_rate=polling_rate,
#             print_rate=print_rate,
#             debug=True,
#             initial_delay=initial_delay,
#             feed_names=["tstfweatherstation.windspeed"],
#             log_to_adafruit_flag=True,
#             print_to_terminal_flag=True,
#             lock=shared_port_lock,
#             min_read_gap=min_read_gap
#         )
#         weather_station.add_sensor("wind_speed", wind_spd)

# # RainGaugeSensor (interrupt-driven, no polling_rate needed)
# rain_sensor = RainGaugeSensor(
#     debug=True,
#     feed_name="tstfweatherstation.raingauge",
#     log_to_adafruit_flag=True,
#     print_to_terminal_flag=True,
#     print_rate=print_rate
# )
# weather_station.add_sensor("rain_gauge", rain_sensor)

# weather_station.start_all()
# # You can stop it with: weather_station.stop_all()



# # run_weather_station.py

# import os
# import time
# from dotenv import load_dotenv
# from Adafruit_IO import Client
# from threading import Lock
# import minimalmodbus

# # Import the library containing all our class definitions
# from weather_station_library import (
#     WeatherStation,
#     ModbusSensor,
#     RainGaugeSensor,
# )

# # --- 1. Load Configuration from Environment ---
# load_dotenv()
# ADAFRUIT_IO_USERNAME = os.getenv("ADAFRUIT_IO_USERNAME")
# ADAFRUIT_IO_KEY = os.getenv("ADAFRUIT_IO_KEY")
# ADAFRUIT_FEED_PREFIX = os.getenv("ADAFRUIT_FEED_PREFIX", "default-weather")

# if not ADAFRUIT_IO_USERNAME or not ADAFRUIT_IO_KEY:
#     print("FATAL: Adafruit IO credentials not found in .env file.")
#     exit()

# print(f"Credentials loaded. Using feed prefix: '{ADAFRUIT_FEED_PREFIX}'")
# aio = Client(ADAFRUIT_IO_USERNAME, ADAFRUIT_IO_KEY)


# # --- 2. Central HARDWARE Configuration ---
# # Station-wide settings
# UPLOAD_RATE = 5 * 60
# PRINT_RATE = 20 * 60
# INITIAL_DELAY = 5
# MIN_READ_GAP = 2

# # Modbus settings
# PORTS_TO_SCAN = ['/dev/ttyUSB0', '/dev/ttyUSB1', '/dev/ttyACM0']
# BAUDRATE = 4800
# TIMEOUT = 2

# # This dictionary now defines ALL hardware-specific details, including calibration.
# SENSOR_CONFIG = {
#     1: {
#         "name": "soil",
#         "polling_rate": 15 * 60,
#         "metrics": {
#             "moisture": {
#                 "register": 0, "decimals": 0,
#                 # Two-point calibration maps the sensor's raw output to a 0-100% scale.
#                 # Find these values by testing your sensor in dry air and pure water.
#                 "correction": {"type": "map", "raw_min": 310, "raw_max": 780}
#             },
#             "temperature": {
#                 "register": 1, "decimals": 1, "signed": True,
#                 # Linear correction: corrected = (raw * factor) + offset
#                 # Example: Fixes a sensor that reads 0.5 degrees too low.
#                 "correction": {"type": "linear", "offset": 0.5, "factor": 1.0}
#             }
#         }
#     },
#     2: {
#         "name": "atmosphere",
#         "polling_rate": 10 * 60,
#         "metrics": {
#             "humidity": {
#                 "register": 0, "decimals": 1,
#                 # Example: Corrects for a sensor that consistently reads 5% too high.
#                 "correction": {"type": "linear", "offset": -5.0}
#              },
#             "temperature": {
#                 "register": 1, "decimals": 1, "signed": True,
#                 # Example: Corrects a sensor that reads 1.1 degrees too high.
#                 "correction": {"type": "linear", "offset": -1.1}
#             }
#         }
#     },
#     3: {
#         "name": "co2",
#         "polling_rate": 5 * 60,
#         # No correction needed for this sensor, so the dictionary is empty.
#         "metrics": {"level": {"register": 0, "decimals": 0, "correction": {}}}
#     },
#     4: {
#         "name": "light",
#         "polling_rate": 5 * 60,
#         "metrics": {
#             "intensity": {
#                 "register": 0, "function": "read_long",
#                 # Example: Apply a scaling factor if the sensor output needs conversion to a standard unit.
#                 "correction": {"type": "linear", "factor": 1.25}
#             }
#         }
#     },
#     5: {
#         "name": "pressure",
#         "polling_rate": 10 * 60,
#         "metrics": {
#             # This sensor outputs Pascals (Pa), but we want to log hectopascals (hPa).
#             # 1 hPa = 100 Pa. A factor of 0.01 will do the conversion.
#             "level": {"register": 0, "decimals": 2, "correction": {"type": "linear", "factor": 0.01}},
#             "temperature": {"register": 1, "decimals": 1, "signed": True, "correction": {}}
#         }
#     },
#      6: {
#         "name": "wind",
#         "polling_rate": 2 * 60,
#         "metrics": {
#             # No correction needed for direction code or speed
#             "direction": {"register": 0, "decimals": 0, "correction": {}},
#             "speed":     {"register": 1, "decimals": 1, "correction": {}}
#         }
#     },
# }

# # Configuration for the Rain Gauge. Update with your calibrated value.
# RAIN_GAUGE_CONFIG = {
#     "name": "rain",
#     "gpio_pin": 17,
#     "mm_per_tip": 0.2765, # Your calibrated value from manual testing
#     "debounce_ms": 250
# }


# # --- 3. Sensor Discovery & Main Execution ---
# def test_sensor(port, address):
#     """Tests for a sensor at a specific port and Modbus address."""
#     try:
#         inst = minimalmodbus.Instrument(port, address)
#         inst.serial.baudrate = BAUDRATE
#         inst.serial.timeout = TIMEOUT
#         _ = inst.read_register(0, 0)
#         return True
#     except (IOError, ValueError):
#         return False

# if __name__ == "__main__":
#     print("\n--- Starting Weather Station ---")
    
#     # Discover connected sensors
#     print("\n--- Sensor Discovery ---")
#     found_addresses = {}
#     for port in PORTS_TO_SCAN:
#         for addr, config in SENSOR_CONFIG.items():
#             if addr not in found_addresses:
#                 print(f"Testing for '{config['name']}' (addr {addr}) on {port}...")
#                 if test_sensor(port, addr):
#                     print(f"  → Found '{config['name']}' on {port}")
#                     found_addresses[addr] = port
#     print("--- Discovery Finished ---\n")

#     # Initialize the station controller
#     shared_port_lock = Lock()
#     weather_station = WeatherStation(
#         aio_client=aio,
#         upload_rate=UPLOAD_RATE,
#         print_rate=PRINT_RATE
#     )

#     # Initialize and add all discovered Modbus sensors
#     for addr, port in found_addresses.items():
#         config = SENSOR_CONFIG[addr]
#         feed_group = config["name"]
        
#         # Automatically generate full feed names from the parts
#         feed_names = [f"{ADAFRUIT_FEED_PREFIX}.{feed_group}-{metric}" for metric in config["metrics"]]
        
#         sensor_instance = ModbusSensor(
#             port=port,
#             address=addr,
#             feed_names=feed_names,
#             metric_configs=config["metrics"], # Pass the detailed metric config with calibration
#             polling_rate=config["polling_rate"],
#             debug=True,
#             initial_delay=INITIAL_DELAY,
#             lock=shared_port_lock,
#             min_read_gap=MIN_READ_GAP,
#             baudrate=BAUDRATE
#         )
#         weather_station.add_sensor(config["name"], sensor_instance)

#     # Initialize and add the Rain Gauge sensor
#     rain_feed_name = f"{ADAFRUIT_FEED_PREFIX}.{RAIN_GAUGE_CONFIG['name']}-total"
#     rain_sensor = RainGaugeSensor(
#         feed_name=rain_feed_name,
#         gpio_pin=RAIN_GAUGE_CONFIG["gpio_pin"],
#         mm_per_tip=RAIN_GAUGE_CONFIG["mm_per_tip"],
#         debounce_ms=RAIN_GAUGE_CONFIG["debounce_ms"],
#         debug=True
#     )
#     weather_station.add_sensor(RAIN_GAUGE_CONFIG["name"], rain_sensor)

#     # Run the station forever
#     try:
#         weather_station.start_all()
#         print("\n--- Weather Station is Running --- (Press Ctrl+C to stop)")
#         while True:
#             time.sleep(1)
#     except KeyboardInterrupt:
#         print("\nShutting down gracefully...")
#         weather_station.stop_all()
#         print("Shutdown complete.")


# run_weather_station.py

import os
import time
import json
from dotenv import load_dotenv
from Adafruit_IO import Client
from threading import Lock
import minimalmodbus

from weather_station_library import (
    WeatherStation, ModbusSensor, RainGaugeSensor,
    AdafruitIOHandler, SQLiteHandler, DataCacheHandler
)

def load_config(path='config.json'):
    """Loads the configuration from the JSON file."""
    with open(path, 'r') as f:
        return json.load(f)

def test_sensor(port, address, baudrate):
    """Tests for a sensor at a specific port and Modbus address."""
    try:
        inst = minimalmodbus.Instrument(port, address)
        inst.serial.baudrate = baudrate
        inst.serial.timeout = 2
        _ = inst.read_register(0, 0)
        return True
    except (IOError, ValueError):
        return False

if __name__ == "__main__":
    load_dotenv()
    aio_user = os.getenv("ADAFRUIT_IO_USERNAME")
    aio_key = os.getenv("ADAFRUIT_IO_KEY")
    aio_prefix = os.getenv("ADAFRUIT_FEED_PREFIX", "default-weather")
    if not aio_user or not aio_key:
        raise Exception("Adafruit IO credentials not found in .env file.")

    print("\n--- Initializing Weather Station Platform ---")
    config = load_config()
    
    # --- Initialize Handlers ---
    print("  Initializing data handlers...")
    aio_client = Client(aio_user, aio_key)
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "weather_data.db")
    
    handlers = [
        AdafruitIOHandler(aio_client=aio_client, feed_prefix=aio_prefix),
        SQLiteHandler(db_path=db_path),
        DataCacheHandler()
    ]

    # --- Initialize Weather Station and Register Handlers ---
    weather_station = WeatherStation(config_path='config.json')
    weather_station.load_config() # Initial load
    for handler in handlers:
        weather_station.add_handler(handler)
        
    # --- Sensor Discovery ---
    print("  Discovering Modbus sensors...")
    found_addrs = {}
    for port in ['/dev/ttyUSB0', '/dev/ttyUSB1', '/dev/ttyACM0', '/dev/ttyACM1']:
        for addr_str, s_conf in config['sensors'].items():
            addr = int(addr_str)
            if addr not in found_addrs and test_sensor(port, addr, 4800):
                print(f"    → Found '{s_conf['name']}' (addr {addr}) on {port}")
                found_addrs[addr] = port

    # --- Add Sensors to Station ---
    shared_lock = Lock()
    for addr, port in found_addrs.items():
        s_conf = config['sensors'][str(addr)]
        # Feed names are still useful for the Adafruit handler and for creating the packet
        feed_names = [f"{aio_prefix}.{s_conf['name']}-{m}" for m in s_conf['metrics']]
        sensor = ModbusSensor(
            name=s_conf['name'], port=port, address=addr, feed_names=feed_names,
            metric_configs=s_conf['metrics'], polling_rate=s_conf['polling_rate'],
            lock=shared_lock, debug=True, initial_delay=5
        )
        weather_station.add_sensor(s_conf['name'], sensor)

    rg_conf = config['rain_gauge']
    rain_feed = f"{aio_prefix}.{rg_conf['name']}-total"
    rain_sensor = RainGaugeSensor(
        name=rg_conf['name'], feed_name=rain_feed, gpio_pin=rg_conf['gpio_pin'],
        gpio_chip=rg_conf['gpio_chip'], mm_per_tip=rg_conf['mm_per_tip'], debug=True
    )
    weather_station.add_sensor(rg_conf['name'], rain_sensor)
    
    # --- Run Forever ---
    try:
        weather_station.start_all()
        print("\n--- Collector Service is Running --- (Press Ctrl+C to stop)")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
        weather_station.stop_all()
        print("Shutdown complete.")