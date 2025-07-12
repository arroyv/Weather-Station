# run_weather_station.py
import os
import time
import json
from dotenv import load_dotenv
from Adafruit_IO import Client
from threading import Thread, Event

from weather_station_library import WeatherStation
from database import DatabaseManager
from handlers import AdafruitIOHandler, LoRaHandler

def load_config(path='config.json'):
    """Loads the configuration from the JSON file."""
    with open(path, 'r') as f:
        return json.load(f)

def get_dynamic_db_path(config):
    """Constructs the database path dynamically."""
    try:
        username = os.getlogin()
        db_config = config.get('database', {})
        drive_label = db_config.get('drive_label')
        
        # Get station name and create the DB filename from it
        station_name = config.get('station_info', {}).get('station_name', 'default-station')
        db_filename = f"{station_name}.db"
        
        if not drive_label:
            raise ValueError("Database 'drive_label' not specified in config.")
            
        path = os.path.join('/media', username, drive_label, db_filename)
        
        # Check if the mount point exists
        if not os.path.exists(os.path.dirname(path)):
            print(f"[Warning] Database directory not found: {os.path.dirname(path)}")
            print("          Please ensure the USB drive is connected and has the correct label.")
            
        return path
    except Exception as e:
        print(f"[Error] Could not determine database path: {e}")
        # Fallback to a local file to prevent crashing
        station_name = config.get('station_info', {}).get('station_name', 'default-station')
        return f"{station_name}.db"

def config_watcher_loop(config_path, weather_station, services, stop_event):
    """
    A central loop that watches for changes in the config file and tells
    all other running services to reload their settings.
    """
    from threading import Lock
    file_lock = Lock()
    
    with file_lock:
        last_mtime = os.path.getmtime(config_path)

    while not stop_event.wait(10): # Check every 10 seconds
        try:
            with file_lock:
                mtime = os.path.getmtime(config_path)
                if mtime > last_mtime:
                    print("\n[ConfigWatcher] Detected config file change. Reloading all services...")
                    last_mtime = mtime
                    
                    new_config = load_config(config_path)
                    
                    # Note: Does not update the database path on the fly. Requires restart.
                    weather_station.update_config(new_config)
                    
                    for service in services:
                        if hasattr(service, 'update_config'):
                            service.update_config(new_config)

        except OSError as e:
            print(f"[ConfigWatcher] ERROR: {e}")

if __name__ == "__main__":
    load_dotenv()
    config = load_config()
    
    station_id = config.get('station_info', {}).get('station_id', 0)
    db_path = get_dynamic_db_path(config)

    print("\n--- Initializing Weather Station Platform ---")
    print(f"  Station ID: {station_id}")

    # 1. Initialize the Database Manager
    db_manager = DatabaseManager(db_path)

    # 2. Initialize the Weather Station to collect data
    weather_station = WeatherStation(config, db_manager=db_manager)
    weather_station.discover_and_add_sensors()
    
    # 3. Initialize all enabled data handlers/services
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

    # 4. Create a shared stop event for graceful shutdown
    stop_event = Event()

    try:
        # Start the main data collection service
        weather_station.start()
        # Start all other data handling services
        for service in all_services:
            service.start()
        
        # Start the central config watcher
        watcher_thread = Thread(target=config_watcher_loop, args=('config.json', weather_station, all_services, stop_event), daemon=True)
        watcher_thread.start()
            
        print("\n--- All Services are Running --- (Press Ctrl+C to stop)")
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
        stop_event.set()
        weather_station.stop()
        for service in all_services:
            service.stop()
        db_manager.close()
        print("Shutdown complete.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        stop_event.set()
        weather_station.stop()
        for service in all_services:
            service.stop()
        db_manager.close()