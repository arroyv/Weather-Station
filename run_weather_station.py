# run_weather_station.py
#TODO: Figure out how to get more fed in adafruit IO or figure out what todo if adafrui IO feed doesn't exist
#TODO: Figure out how the rain guige data will be sen t shoudl it be accumulated every minute hour or day and then send saved. Zero should be sent if no rain has fallen during accumulation period?
#TODO: Figure out how to toggle the diffrent data handlers on and off
#TODO: Reduce the number of ports to scan by checking the config file for the ports that are actually used
#TODO: Write flaks based dash board code that uses the SQLite database to display the data in a web browser and controll the sensors rates toggle data handlers and other settings.
#TODO: Set up MCP server to allow LLM to access the data and control the sensors and graph using jupyter notebook
#TODO: Try out TimeGPTModel API for tim series analysis and prediction
#TODO: Re set up auto startng the python program instructions and Set up of the respberry pi instructions and read me
#TODO: write instruction on how to set up local files needed .env file and config.json file
#TODO: implemet sleep state to svae power, also find way to reduce power consumtpion of the sensors and the raspberry pi
# Wite doesn notes for problem to check  like ckec wifi rssi to see if wifi connection is solid, make sure ther is nothing in th way of the antenna
# figure out how to add a usb wifi anterna to the raspberry pi to improve wifi signal
# find seom seather proof boses for the raspberry pi

import os
import time
import json
from dotenv import load_dotenv
from Adafruit_IO import Client
from threading import Lock

from weather_station_library import (
    WeatherStation, ModbusSensor, RainGaugeSensor,
    AdafruitIOHandler, SQLiteHandler, DataCacheHandler
)

def load_config(path='config.json'):
    """Loads the configuration from the JSON file."""
    with open(path, 'r') as f:
        return json.load(f)

# The test_sensor function is now part of the WeatherStation class,
# so it is no longer needed here.

if __name__ == "__main__":
    load_dotenv()
    aio_user = os.getenv("ADAFRUIT_IO_USERNAME")
    aio_key = os.getenv("ADAFRUIT_IO_KEY")
    aio_prefix = os.getenv("ADAFRUIT_FEED_PREFIX", "default-weather")
    if not aio_user or not aio_key:
        raise Exception("Adafruit IO credentials not in .env file.")

    print("\n--- Initializing Weather Station Platform ---")
    config = load_config()
    
    print("  Initializing data handlers...")
    aio_client = Client(aio_user, aio_key)
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "weather_data.db")
    
    # Pass the full config to the AdafruitIOHandler so it can find the explicit feed_key for each metric.
    handlers = [
        AdafruitIOHandler(aio_client=aio_client, feed_prefix=aio_prefix, full_config=config),
        SQLiteHandler(db_path=db_path),
        DataCacheHandler()
    ]

    # Initialize Weather Station and pass it info needed for re-discovery
    weather_station = WeatherStation(config_path='config.json')
    weather_station.load_config()
    weather_station.shared_modbus_lock = Lock()
    weather_station.ports_to_scan = [
        '/dev/ttyUSB0', '/dev/ttyUSB1', '/dev/ttyUSB2', '/dev/ttyUSB3',
        '/dev/ttyACM0', '/dev/ttyACM1', '/dev/ttyACM2', '/dev/ttyACM3',
        '/dev/ttyS0', '/dev/ttyAMA0', '/dev/serial0', '/dev/serial1'
    ]
    
    for handler in handlers:
        weather_station.add_handler(handler)
        
    print(f"  Performing initial discovery of Modbus sensors across {len(weather_station.ports_to_scan)} potential ports...")
    found_addrs = {}
    for addr_str, s_conf in config['sensors'].items():
        addr = int(addr_str)
        # Scan all available ports for this sensor
        for port in weather_station.ports_to_scan:
            if os.path.exists(port):
                # Use the test method from the weather_station object
                if weather_station._test_sensor_at_location(port, addr, 4800):
                    print(f"    → Found '{s_conf['name']}' (addr {addr}) on {port}")
                    found_addrs[addr] = port
                    break # Stop scanning for this sensor since we found it

    # Add all discovered Modbus sensors to the station
    for addr, port in found_addrs.items():
        s_conf = config['sensors'][str(addr)]
        sensor = ModbusSensor(
            name=s_conf['name'], port=port, address=addr,
            metric_configs=s_conf['metrics'], 
            polling_rate=s_conf['polling_rate'],
            lock=weather_station.shared_modbus_lock, 
            debug=True, 
            initial_delay=5
        )
        weather_station.add_sensor(s_conf['name'], sensor)

    # Add the Rain Gauge (it is not discoverable)
    rg_conf = config['rain_gauge']
    rain_sensor = RainGaugeSensor(
        name=rg_conf['name'],
        metric=rg_conf['metric'],
        gpio_pin=rg_conf['gpio_pin'],
        mm_per_tip=rg_conf['mm_per_tip'],
        debug=True,
        debounce_ms=rg_conf['debounce_ms']
    )
    weather_station.add_sensor(rg_conf['name'], rain_sensor)
    
    try:
        weather_station.start_all()
        print("\n--- Collector Service is Running --- (Press Ctrl+C to stop)")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
        weather_station.stop_all()
        print("Shutdown complete.")