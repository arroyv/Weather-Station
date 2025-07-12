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
station_db_map = {}
map_lock = Lock()

def load_config():
    with config_lock:
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f)

def get_all_db_paths(local_db_path):
    db_dir = os.path.dirname(local_db_path)
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
                    db_manager = DatabaseManager(db_file)
                    data = db_manager.get_latest_readings_by_station()
                    latest_data_by_station.update(data)
                    for station_id in data.keys():
                        station_db_map[station_id] = db_file
                    db_manager.close()
                except Exception as e:
                    print(f"[Dashboard] ERROR reading from {db_file}: {e}")
        
        # --- Wind Direction Text Conversion ---
        direction_map = { 0: "N", 1: "NE", 2: "E", 3: "SE", 4: "S", 5: "SW", 6: "W", 7: "NW" }

        for station_id, readings in latest_data_by_station.items():
            for key, reading in readings.items():
                sensor_name, metric_name = reading['sensor'], reading['metric']
                label, unit = key, ""
                
                if sensor_name == 'wind-direction' and metric_name == 'direction':
                    label, unit = "Wind Direction", ""
                    reading_dict = dict(reading)
                    reading_dict['display_value'] = direction_map.get(int(reading['value']), 'Unknown')
                else:
                    if sensor_name == config.get('rain_gauge', {}).get('name'):
                        label, unit = config['rain_gauge'].get('label', sensor_name), config['rain_gauge'].get('unit', '')
                    else:
                        for s_conf in config.get('sensors', {}).values():
                            if s_conf.get('name') == sensor_name:
                                metric_conf = s_conf.get('metrics', {}).get(metric_name, {})
                                label, unit = metric_conf.get('label', key), metric_conf.get('unit', '')
                                break
                    reading_dict = dict(reading)
                
                reading_dict['label'] = label
                reading_dict['unit'] = unit
                latest_data_by_station[station_id][key] = reading_dict
        
        cache['data'] = latest_data_by_station
        cache['last_updated'] = now
        return cache['data']

@app.route('/api/history/<int:station_id>/<string:sensor_key>/<int:hours>')
def get_history(station_id, sensor_key, hours):
    with map_lock:
        db_path = station_db_map.get(station_id)

    if not db_path:
        return jsonify({"error": "Station not found or map not populated"}), 404

    try:
        sensor_name, metric_name = sensor_key.split('-', 1)
        db = DatabaseManager(db_path)
        all_history = db.get_historical_data(station_id, hours)
        db.close()

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
    config = load_config()
    enriched_data = get_enriched_data()
    station_tabs = []
    local_station_id = config.get('station_info', {}).get('station_id')
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

# The /settings route remains the same...
@app.route('/settings', methods=['GET', 'POST'])
def settings():
    # ...
    return render_template('settings.html', config=load_config())

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)