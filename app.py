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
app.secret_key = os.getenv('SECRET_KEY', 'a-secure-default-fallback-key-for-development')
config_lock = Lock()

# --- Caching and DB Mapping ---
cache = {'data': None, 'last_updated': 0}
CACHE_LIFETIME_SECONDS = 10
cache_lock = Lock()

# This map will store which station ID corresponds to which DB file
station_db_map = {}
map_lock = Lock()

def load_config():
    with config_lock:
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f)

def save_config(new_config):
    # ... (save_config function remains the same)
    with config_lock:
        with open(CONFIG_PATH, 'w') as f:
            json.dump(new_config, f, indent=2)

def get_all_db_paths(local_db_path):
    # ... (get_all_db_paths function remains the same)
    db_dir = os.path.dirname(local_db_path)
    return glob.glob(os.path.join(db_dir, '*.db'))

def get_enriched_data():
    """Gathers data from all available database files, using a cache."""
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
            station_db_map.clear() # Clear the map before rebuilding
            for db_file in all_db_files:
                try:
                    db_manager = DatabaseManager(db_file)
                    data = db_manager.get_latest_readings_by_station()
                    latest_data_by_station.update(data)
                    # Populate the station_id -> db_path map
                    for station_id in data.keys():
                        station_db_map[station_id] = db_file
                    db_manager.close()
                except Exception as e:
                    print(f"[Dashboard] ERROR reading from {db_file}: {e}")

        for station_id, readings in latest_data_by_station.items():
            for key, reading in readings.items():
                sensor_name, metric_name = reading['sensor'], reading['metric']
                label, unit = key, ""
                # ... (rest of enrichment logic is the same)
                if sensor_name == config.get('rain_gauge', {}).get('name'):
                    label, unit = config['rain_gauge'].get('label', sensor_name), config['rain_gauge'].get('unit', '')
                else:
                    for s_conf in config.get('sensors', {}).values():
                        if s_conf.get('name') == sensor_name:
                            metric_conf = s_conf.get('metrics', {}).get(metric_name)
                            if metric_conf: label, unit = metric_conf.get('label', key), metric_conf.get('unit', '')
                            break
                reading_dict = dict(reading); reading_dict['label'] = label; reading_dict['unit'] = unit
                latest_data_by_station[station_id][key] = reading_dict
        
        cache['data'] = latest_data_by_station
        cache['last_updated'] = now
        return cache['data']

# --- API Endpoint for Graph Data ---
@app.route('/api/history/<int:station_id>/<string:sensor_key>/<int:hours>')
def get_history(station_id, sensor_key, hours):
    with map_lock:
        db_path = station_db_map.get(station_id)

    if not db_path:
        return jsonify({"error": "Station not found or map not populated"}), 404

    try:
        sensor_name, metric_name = sensor_key.split('-', 1)
        db = DatabaseManager(db_path)
        # The underlying query gets all data, we filter it here
        all_history = db.get_historical_data(station_id, hours)
        db.close()

        # Filter for the specific metric we want
        filtered_data = [
            {"timestamp": row["timestamp"], "value": row["value"]}
            for row in all_history
            if row["sensor"] == sensor_name and row["metric"] == metric_name
        ]
        return jsonify(filtered_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/')
def dashboard():
    # ... (dashboard route remains the same)
    config = load_config()
    enriched_data = get_enriched_data()
    station_tabs, local_station_id = [], config.get('station_info', {}).get('station_id')
    sorted_station_ids = sorted(enriched_data.keys())
    
    if local_station_id in sorted_station_ids:
        sorted_station_ids.insert(0, sorted_station_ids.pop(sorted_station_ids.index(local_station_id)))
        
    for station_id in sorted_station_ids:
        station_tabs.append({
            'id': station_id,
            'name': f"Station {station_id}" + (" (Local)" if station_id == local_station_id else " (Remote)"),
            'data': dict(sorted(enriched_data.get(station_id, {}).items()))
        })
        
    return render_template('dashboard.html', station_tabs=station_tabs)

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    # ... (settings route remains the same)
    if request.method == 'POST':
        try:
            current_config = load_config()
            current_config['services']['adafruit_io_enabled'] = 'adafruit_io_enabled' in request.form
            current_config['services']['lora_enabled'] = 'lora_enabled' in request.form
            current_config['station_info']['station_name'] = request.form.get('station_name', 'default-name')
            
            current_config['timing']['transmission_interval_seconds'] = max(1, request.form.get('transmission_interval_seconds', 60, type=int))
            current_config['timing']['adafruit_io_interval_seconds'] = max(10, request.form.get('adafruit_io_interval_seconds', 300, type=int))
            current_config['lora']['role'] = request.form.get('lora_role', 'base')
            current_config['lora']['frequency'] = float(request.form.get('lora_frequency', 915.0))
            current_config['lora']['tx_power'] = min(23, max(5, request.form.get('lora_tx_power', 23, type=int)))

            for sensor_id, sensor_config in current_config.get('sensors', {}).items():
                current_config['sensors'][sensor_id]['enabled'] = f"enabled_{sensor_config['name']}" in request.form
                rate = request.form.get(f"polling_rate_{sensor_config['name']}", type=int)
                current_config['sensors'][sensor_id]['polling_rate'] = max(1, rate) if rate is not None else 60
            
            if 'rain_gauge' in current_config:
                current_config['rain_gauge']['enabled'] = 'enabled_rain' in request.form

            save_config(current_config)
            flash("Configuration saved successfully! Changes will be applied on the next cycle.", "success")
        except (ValueError, TypeError) as e:
            flash(f"Error saving configuration: Invalid input. Please check your values. ({e})", "danger")
        except Exception as e:
            flash(f"Error saving configuration: {e}", "danger")
        return redirect(url_for('settings'))
    config = load_config()
    return render_template('settings.html', config=config)


if __name__ == '__main__':
    print("--- Starting Weather Station Dashboard & API ---")
    print(f"Access the dashboard at http://127.0.0.1:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)