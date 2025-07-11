# app.py
import os
import json
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from threading import Lock
from database import DatabaseManager

# --- Configuration ---
project_dir = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(project_dir, 'config.json')
DB_PATH = os.path.join(project_dir, 'weather_data.db')

app = Flask(__name__)
app.secret_key = 'super-secret-key-for-weather-station' 
config_lock = Lock()

# --- Initialize Database Manager ---
db_manager = DatabaseManager(DB_PATH)

def load_config():
    with config_lock:
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f)

def save_config(new_config):
    with config_lock:
        with open(CONFIG_PATH, 'w') as f:
            json.dump(new_config, f, indent=2)

def get_enriched_data():
    config = load_config()
    latest_data_by_station = db_manager.get_latest_readings_by_station()
    for station_id, readings in latest_data_by_station.items():
        for key, reading in readings.items():
            sensor_name, metric_name = reading['sensor'], reading['metric']
            label, unit = key, ""
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
    return latest_data_by_station

@app.route('/')
def dashboard():
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
            'data': dict(sorted(enriched_data[station_id].items()))
        })
    return render_template('dashboard.html', station_name=config.get('station_info', {}).get('station_name', 'Unknown'), station_tabs=station_tabs)

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if request.method == 'POST':
        try:
            current_config = load_config()
            current_config['services']['adafruit_io_enabled'] = 'adafruit_io_enabled' in request.form
            current_config['services']['lora_enabled'] = 'lora_enabled' in request.form
            current_config['station_info']['station_name'] = request.form.get('station_name', 'default-name')
            current_config['timing']['transmission_interval_seconds'] = request.form.get('transmission_interval_seconds', 60, type=int)
            current_config['timing']['adafruit_io_interval_seconds'] = request.form.get('adafruit_io_interval_seconds', 300, type=int)
            current_config['lora']['role'] = request.form.get('lora_role', 'base')
            current_config['lora']['frequency'] = request.form.get('lora_frequency', 915.0, type=float)
            current_config['lora']['tx_power'] = request.form.get('lora_tx_power', 23, type=int)
            current_config['lora']['local_address'] = request.form.get('lora_local_address', 1, type=int)
            current_config['lora']['remote_address'] = request.form.get('lora_remote_address', 2, type=int)

            if 'remote_config_payload' in current_config:
                for sensor_id, sensor_config in current_config['remote_config_payload'].get('sensors', {}).items():
                    field_name = f"remote_polling_rate_{sensor_id}"
                    new_rate = request.form.get(field_name, type=int)
                    if new_rate is not None:
                        current_config['remote_config_payload']['sensors'][sensor_id]['polling_rate'] = new_rate

            for sensor_id, sensor_config in current_config.get('sensors', {}).items():
                current_config['sensors'][sensor_id]['enabled'] = f"enabled_{sensor_config['name']}" in request.form
                current_config['sensors'][sensor_id]['polling_rate'] = request.form.get(f"polling_rate_{sensor_config['name']}", type=int)
            if 'rain_gauge' in current_config:
                current_config['rain_gauge']['enabled'] = 'enabled_rain' in request.form

            save_config(current_config)
            flash("Configuration saved successfully! Changes will be applied on the next cycle.", "success")
        except Exception as e:
            flash(f"Error saving configuration: {e}", "danger")
        return redirect(url_for('settings'))
    config = load_config()
    return render_template('settings.html', config=config)

if __name__ == '__main__':
    print("--- Starting Weather Station Dashboard & API ---")
    print(f"Access the dashboard at http://127.0.0.1:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
