# app.py
import os
import json
import glob
import time 
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from threading import Lock
from database import DatabaseManager
from run_weather_station import get_dynamic_db_path as get_local_db_path

# --- Configuration ---
project_dir = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(project_dir, 'config.json')

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'a-very-secret-key')
config_lock = Lock()

# --- Caching and DB Mapping ---
cache = {'data': None, 'last_updated': 0}
CACHE_LIFETIME_SECONDS = 10
cache_lock = Lock()
station_db_map = {}
map_lock = Lock()

def load_config():
    with config_lock:
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f)

def save_config(config_data):
    with config_lock:
        with open(CONFIG_PATH, 'w') as f:
            json.dump(config_data, f, indent=2)

def get_all_db_paths(local_db_path):
    db_dir = os.path.dirname(local_db_path)
    if not os.path.isdir(db_dir):
        return []
    return glob.glob(os.path.join(db_dir, '*.db'))

def get_enriched_data():
    with cache_lock:
        now = time.time()
        if cache['data'] and (now - cache['last_updated'] < CACHE_LIFETIME_SECONDS):
            return cache['data']

        print("[Dashboard] Cache expired. Rebuilding data from databases.")
        config = load_config()
        local_db_path = get_local_db_path(config)
        all_db_files = get_all_db_paths(local_db_path)
        
        latest_data_by_station = {}
        
        with map_lock:
            station_db_map.clear()
            for db_file in all_db_files:
                try:
                    # Use a temporary DB manager to avoid holding connections
                    db_manager = DatabaseManager(db_file)
                    data = db_manager.get_latest_readings_by_station()
                    for station_id in data.keys():
                        station_db_map[station_id] = db_file
                    latest_data_by_station.update(data)
                    db_manager.close()
                except Exception as e:
                    print(f"[Dashboard] ERROR reading from {db_file}: {e}")
        
        # Enrich data with labels and units from config
        for station_id, readings in latest_data_by_station.items():
            for key, reading in readings.items():
                sensor_name = reading['sensor']
                metric_name = reading['metric']
                
                # Find the label and unit from the config file
                label, unit = key, ""
                sensor_found = False
                for s_conf in config.get('sensors', {}).values():
                    if s_conf['name'] == sensor_name:
                        metric_conf = s_conf.get('metrics', {}).get(metric_name)
                        if metric_conf:
                            label = metric_conf.get('label', key)
                            unit = metric_conf.get('unit', '')
                        sensor_found = True
                        break
                if not sensor_found:
                    rg_conf = config.get('rain_gauge', {})
                    if rg_conf.get('name') == sensor_name:
                         label = rg_conf.get('label', key)
                         unit = rg_conf.get('unit', '')
                
                reading['label'] = label
                reading['unit'] = unit

        cache['data'] = latest_data_by_station
        cache['last_updated'] = now
        return cache['data']

@app.route('/api/history/<int:station_id>/<string:sensor_key>/<int:hours>')
def get_history(station_id, sensor_key, hours):
    with map_lock:
        db_path = station_db_map.get(station_id)

    if not db_path:
        return jsonify({"error": "Station database not found"}), 404

    try:
        # Load the config to get a list of valid sensor names
        config = load_config()
        known_sensor_names = [s['name'] for s in config.get('sensors', {}).values()]
        if 'rain_gauge' in config:
            known_sensor_names.append(config['rain_gauge']['name'])

        sensor = None
        metric = None

        # Sort by length (descending) to match longer names first (e.g., 'wind-speed' before 'wind')
        for s_name in sorted(known_sensor_names, key=len, reverse=True):
            # Check if the key starts with the sensor name followed by a hyphen
            if sensor_key.startswith(s_name + '-'):
                sensor = s_name
                # The metric is the rest of the string after the sensor name and hyphen
                metric = sensor_key[len(s_name) + 1:]
                break
        
        if not sensor:
            raise ValueError(f"Could not determine sensor from key: '{sensor_key}'")

        db = DatabaseManager(db_path)
        historical_data = db.get_historical_data(station_id, sensor, metric, hours)
        db.close()
        return jsonify(historical_data)
    except ValueError as e:
         return jsonify({"error": f"Invalid sensor key format. {e}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/')
def dashboard():
    config = load_config()
    enriched_data = get_enriched_data()
    station_tabs = []
    local_station_id = config.get('station_info', {}).get('station_id')
    
    # Sort stations to have a consistent order, with local station first
    sorted_station_ids = sorted(enriched_data.keys())
    if local_station_id in sorted_station_ids:
        sorted_station_ids.insert(0, sorted_station_ids.pop(sorted_station_ids.index(local_station_id)))
        
    for station_id in sorted_station_ids:
        db_path = station_db_map.get(station_id, "Unknown DB")
        db_name = os.path.basename(db_path)
        is_local = (station_id == local_station_id)

        station_tabs.append({
            'id': station_id,
            'db_name': db_name,
            'is_local': is_local,
            'data': dict(sorted(enriched_data.get(station_id, {}).items()))
        })
        
    return render_template('dashboard.html', station_tabs=station_tabs)

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if request.method == 'POST':
        try:
            current_config = load_config()
            # General Services
            current_config['services']['adafruit_io_enabled'] = 'adafruit_io_enabled' in request.form
            current_config['services']['lora_enabled'] = 'lora_enabled' in request.form
            
            # Station Info
            current_config['station_info']['station_name'] = request.form.get('station_name', 'default-name')
            
            # Timing
            current_config['timing']['transmission_interval_seconds'] = max(5, request.form.get('transmission_interval_seconds', 60, type=int))
            current_config['timing']['adafruit_io_interval_seconds'] = max(10, request.form.get('adafruit_io_interval_seconds', 300, type=int))
            
            # LoRa Config
            current_config['lora']['role'] = request.form.get('lora_role', 'base')
            current_config['lora']['frequency'] = float(request.form.get('lora_frequency', 915.0))
            current_config['lora']['tx_power'] = min(23, max(5, request.form.get('lora_tx_power', 23, type=int)))
            current_config['lora']['base_station_address'] = int(request.form.get('base_station_address', 1))

            # Sensor Config
            for sensor_id, sensor_config in current_config.get('sensors', {}).items():
                sensor_name = sensor_config['name']
                current_config['sensors'][sensor_id]['enabled'] = f"enabled_{sensor_name}" in request.form
                rate = request.form.get(f"polling_rate_{sensor_name}", 60, type=int)
                current_config['sensors'][sensor_id]['polling_rate'] = max(10, rate)
            
            if 'rain_gauge' in current_config:
                current_config['rain_gauge']['enabled'] = 'enabled_rain' in request.form

            save_config(current_config)
            flash("Configuration saved successfully! A restart may be required for some changes to take effect.", "success")
        except (ValueError, TypeError) as e:
            flash(f"Error saving configuration: Invalid input. ({e})", "danger")
        except Exception as e:
            flash(f"Error saving configuration: {e}", "danger")
        return redirect(url_for('settings'))
    
    config = load_config()
    return render_template('settings.html', config=config)

if __name__ == '__main__':
    # Use 0.0.0.0 to make it accessible on the network
    app.run(host='0.0.0.0', port=5000, debug=True)
