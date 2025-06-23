# run_weather_station.py

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
    print("  [Config] Loading configuration...")
    with open(self.config_path, 'r') as f:
        self.config = json.load(f)

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