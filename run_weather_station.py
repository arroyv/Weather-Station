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
        raise Exception("Adafruit IO credentials not in .env file.")

    print("\n--- Initializing Weather Station Platform ---")
    config = load_config()
    
    print("  Initializing data handlers...")
    aio_client = Client(aio_user, aio_key)
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "weather_data.db")
    
    handlers = [
        AdafruitIOHandler(aio_client=aio_client, feed_prefix=aio_prefix),
        SQLiteHandler(db_path=db_path),
        DataCacheHandler()
    ]

    weather_station = WeatherStation(config_path='config.json')
    weather_station.load_config() # Initial load
    for handler in handlers:
        weather_station.add_handler(handler)
        
    print("  Discovering Modbus sensors...")
    found_addrs = {}
    for port in ['/dev/ttyUSB0', '/dev/ttyUSB1', '/dev/ttyACM0', '/dev/ttyACM1']:
        for addr_str, s_conf in config['sensors'].items():
            addr = int(addr_str)
            if addr not in found_addrs and test_sensor(port, addr, 4800):
                print(f"    → Found '{s_conf['name']}' (addr {addr}) on {port}")
                found_addrs[addr] = port

    shared_lock = Lock()
    for addr, port in found_addrs.items():
        s_conf = config['sensors'][str(addr)]
        feed_names = [f"{aio_prefix}.{s_conf['name']}-{m}" for m in s_conf['metrics']]
        sensor = ModbusSensor(
            name=s_conf['name'], port=port, address=addr, feed_names=feed_names,
            metric_configs=s_conf['metrics'], polling_rate=s_conf['polling_rate'],
            lock=shared_lock, debug=True, initial_delay=5
        )
        weather_station.add_sensor(s_conf['name'], sensor)

    # NEW, CORRECTED BLOCK
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