# run_weather_station.py
import os
import time
import json
from dotenv import load_dotenv
from Adafruit_IO import Client
from threading import Lock, Thread, Event

from weather_station_library import WeatherStation, ModbusSensor, RainGaugeSensor
from database import DatabaseManager
from handlers import AdafruitIOHandler, LoRaHandler, WiFiSyncHandler

def load_config(path='config.json'):
    """Loads the configuration from the JSON file."""
    with open(path, 'r') as f:
        return json.load(f)

if __name__ == "__main__":
    load_dotenv()
    config = load_config()
    
    station_id = config.get('station_info', {}).get('station_id', 0)
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), config.get('database', {}).get('path', 'weather_data.db'))

    print("\n--- Initializing Weather Station Platform ---")
    print(f"  Station ID: {station_id}")

    # 1. Initialize the Database Manager (the central hub)
    db_manager = DatabaseManager(db_path)

    # 2. Initialize the Weather Station to collect data
    weather_station = WeatherStation(config_path='config.json', db_manager=db_manager)
    weather_station.load_config() # Initial load
    weather_station.discover_and_add_sensors()
    
    # 3. Initialize and start all enabled data handlers/services
    all_services = []
    services_config = config.get('services', {})

    if services_config.get('adafruit_io_enabled'):
        aio_user = os.getenv("ADAFRUIT_IO_USERNAME")
        aio_key = os.getenv("ADAFRUIT_IO_KEY")
        aio_prefix = os.getenv("ADAFRUIT_FEED_PREFIX", "default-weather")
        if aio_user and aio_key:
            aio_client = Client(aio_user, aio_key)
            aio_handler = AdafruitIOHandler(config, db_manager, aio_client, aio_prefix)
            all_services.append(aio_handler)
        else:
            print("[Warning] Adafruit IO is enabled in config, but credentials are not in .env file.")

    if services_config.get('lora_enabled'):
        lora_handler = LoRaHandler(config, db_manager)
        all_services.append(lora_handler)

    if services_config.get('wifi_sync_enabled'):
        wifi_handler = WiFiSyncHandler(config, db_manager)
        all_services.append(wifi_handler)

    try:
        # Start the main data collection service
        weather_station.start_all()
        # Start all other data handling services
        for service in all_services:
            service.start()
            
        print("\n--- All Services are Running --- (Press Ctrl+C to stop)")
        # The main thread just needs to keep the program alive
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
        weather_station.stop_all()
        for service in all_services:
            service.stop()
        db_manager.close()
        print("Shutdown complete.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        # Perform cleanup
        weather_station.stop_all()
        for service in all_services:
            service.stop()
        db_manager.close()

