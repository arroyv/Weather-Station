# run_weather_station.py
import os
import time
import json
import argparse
from dotenv import load_dotenv
from Adafruit_IO import Client
from threading import Thread, Event

from weather_station_library import WeatherStation
from database import DatabaseManager
from handlers import AdafruitIOHandler, LoRaHandler

def load_config(path='config.json'):
    if not os.path.exists(path):
        print(f"[{__name__}] Config file not found. Creating from template...")
        template_path = path + '.template'
        if os.path.exists(template_path):
            with open(template_path, 'r') as f_template:
                with open(path, 'w') as f_config:
                    f_config.write(f_template.read())
        else:
            raise FileNotFoundError("config.json and config.json.template not found.")

    with open(path, 'r') as f:
        return json.load(f)

def get_dynamic_db_path(config):
    try:
        username = os.getlogin()
        db_config = config.get('database', {})
        drive_label = db_config.get('drive_label')
        
        station_name = config.get('station_info', {}).get('station_name', 'default-station')
        db_filename = f"{station_name}.db"
        
        if not drive_label:
            raise ValueError("Database 'drive_label' not specified in config.")
            
        path = os.path.join('/media', username, drive_label, db_filename)
        
        if not os.path.exists(os.path.dirname(path)):
            print(f"[Warning] Database directory not found: {os.path.dirname(path)}")
            
        return path
    except Exception as e:
        print(f"[Error] Could not determine database path: {e}")
        station_name = config.get('station_info', {}).get('station_name', 'default-station')
        return f"{station_name}.db"

def config_watcher_loop(config_path, weather_station, services, stop_event):
    from threading import Lock
    file_lock = Lock()
    
    with file_lock:
        last_mtime = os.path.getmtime(config_path)

    while not stop_event.wait(10):
        try:
            with file_lock:
                mtime = os.path.getmtime(config_path)
                if mtime > last_mtime:
                    print("\n[ConfigWatcher] Detected config file change. Reloading all services...")
                    last_mtime = mtime
                    
                    new_config = load_config(config_path)
                    
                    weather_station.update_config(new_config)
                    
                    for service in services:
                        if hasattr(service, 'update_config'):
                            service.update_config(new_config)
        except OSError as e:
            print(f"[ConfigWatcher] ERROR: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Weather Station application.")
    parser.add_argument('--name', type=str, help="The name of this station (overrides config file).")
    parser.add_argument('--role', type=str, choices=['base', 'remote'], help="The LoRa role for this station (overrides config file).")
    parser.add_argument('--id', type=int, help="The unique ID of this station (overrides config file).")
    args = parser.parse_args()

    load_dotenv()
    config = load_config()
    
    if args.name:
        config['station_info']['station_name'] = args.name
        print(f"[Startup] Overriding station name with command-line arg: {args.name}")
    if args.role:
        config['lora']['role'] = args.role
        print(f"[Startup] Overriding LoRa role with command-line arg: {args.role}")
    if args.id is not None:
        config['station_info']['station_id'] = args.id
        print(f"[Startup] Overriding station ID with command-line arg: {args.id}")

    station_id = config.get('station_info', {}).get('station_id')
    db_path = get_dynamic_db_path(config)

    print("\n--- Initializing Weather Station Platform ---")
    print(f"  Station Name: {config['station_info']['station_name']}")
    print(f"  Station ID: {station_id}")
    print(f"  LoRa Role: {config['lora']['role']}")

    db_manager = DatabaseManager(db_path)

    weather_station = WeatherStation(config, db_manager=db_manager)
    weather_station.discover_and_add_sensors()
    
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

    stop_event = Event()

    try:
        weather_station.start()
        for service in all_services:
            service.start()
        
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