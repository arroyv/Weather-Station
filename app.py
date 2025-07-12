# app.py
import os
import json
import glob
import time 
import sqlite3
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

def build_metric_info_map(config):
    """Builds a lookup map from DB column name to its label and unit."""
    metric_map = {}
    for s_conf in config.get('sensors', {}).values():
        for metric, m_conf in s_conf.get('metrics', {}).items():
            col_name = f"{s_conf['name']}_{metric.replace('-', '_')}"
            metric_map[col_name] = {'label': m_conf.get('label', col_name), 'unit': m_conf.get('unit', '')}
    if config.get('rain_gauge', {}).get('enabled'):
        rg_conf = config['rain_gauge']
        col_name = f"{rg_conf['name']}_{rg_conf['metric']}"
        metric_map[col_name] = {'label': rg_conf.get('label', col_name), 'unit': rg_conf.get('unit', '')}
    metric_map['rssi'] = {'label': 'RSSI', 'unit': 'dBm'}
    return metric_map

def get_enriched_data():
    with cache_lock:
        now = time.time()
        if cache['data'] and (now - cache['last_updated'] < CACHE_LIFETIME_SECONDS):
            return cache['data']

        print("[Dashboard] Cache expired. Rebuilding data from databases.")
        config = load_config()
        metric_info_map = build_metric_info_map(config)
        local_db_path = get_local_db_path(config)
        all_db_files = get_all_db_paths(local_db_path)
        
        latest_data_by_station = {}
        
        with map_lock:
            station_db_map.clear()
            for db_file in all_db_files:
                try:
                    db_manager = DatabaseManager(db_file, config)
                    temp_conn = sqlite3.connect(db_file)
                    cursor = temp_conn.cursor()
                    cursor.execute("SELECT DISTINCT station_id FROM snapshots")
                    station_ids_in_db = [row[0] for row in cursor.fetchall()]
                    temp_conn.close()

                    for station_id in station_ids_in_db:
                        data = db_manager.get_latest_snapshot(station_id)
                        if data:
                            latest_data_by_station[station_id] = data
                            station_db_map[station_id] = db_file
                    db_manager.close()
                except Exception as e:
                    print(f"[Dashboard] ERROR reading from {db_file}: {e}")
        
        enriched_data = {}
        direction_map = { 0: "N", 1: "NE", 2: "E", 3: "SE", 4: "S", 5: "SW", 6: "W", 7: "NW" }

        for station_id, snapshot in latest_data_by_station.items():
            enriched_data[station_id] = {}
            if not snapshot: continue
            
            for col_name, value in snapshot.items():
                if value is None or col_name in ['id', 'timestamp', 'station_id']:
                    continue
                
                info = metric_info_map.get(col_name, {'label': col_name, 'unit': ''})
                
                # Reconstruct the original key format (e.g., 'soil-temp-c') for the template
                parts = col_name.split('_', 1)
                original_key = f"{parts[0]}-{parts[1].replace('_', '-')}" if len(parts) > 1 else parts[0]
                
                reading = {
                    'value': value,
                    'label': info['label'],
                    'unit': info['unit'],
                    'timestamp': snapshot['timestamp']
                }

                # Special handling for wind direction display
                if col_name == 'wind_direction_direction':
                    reading['display_value'] = direction_map.get(int(value), 'Unknown')
                
                enriched_data[station_id][original_key] = reading

        cache['data'] = enriched_data
        cache['last_updated'] = now
        return cache['data']

@app.route('/api/history/<int:station_id>/<string:sensor_key>/<int:hours>')
def get_history(station_id, sensor_key, hours):
    with map_lock:
        db_path = station_db_map.get(station_id)

    if not db_path:
        return jsonify({"error": "Station not found or map not populated"}), 404

    try:
        config = load_config()
        db = DatabaseManager(db_path, config)
        # Convert sensor_key back to a valid SQL column name
        metric_column = sensor_key.replace('-', '_')
        historical_data = db.get_historical_data(station_id, hours, metric_column)
        db.close()
        return jsonify(historical_data)
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
            # ... (rest of settings POST logic is the same)
            save_config(current_config)
            flash("Configuration saved successfully!", "success")
        except Exception as e:
            flash(f"Error saving configuration: {e}", "danger")
        return redirect(url_for('settings'))
    config = load_config()
    return render_template('settings.html', config=config)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)