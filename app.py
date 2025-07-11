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
    """Helper to load the main config file."""
    with config_lock:
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f)

def save_config(new_config):
    """Helper to save the main config file."""
    with config_lock:
        with open(CONFIG_PATH, 'w') as f:
            json.dump(new_config, f, indent=2)

def get_enriched_data():
    """
    Gets the latest data from the DB and enriches it with labels and units.
    """
    config = load_config()
    latest_data_by_station = db_manager.get_latest_readings_by_station()
    
    for station_id, readings in latest_data_by_station.items():
        for key, reading in readings.items():
            sensor_name = reading['sensor']
            metric_name = reading['metric']
            
            label = key
            unit = ""

            if sensor_name == config.get('rain_gauge', {}).get('name'):
                label = config['rain_gauge'].get('label', sensor_name)
                unit = config['rain_gauge'].get('unit', '')
            else:
                for s_conf in config.get('sensors', {}).values():
                    if s_conf.get('name') == sensor_name:
                        metric_conf = s_conf.get('metrics', {}).get(metric_name)
                        if metric_conf:
                            label = metric_conf.get('label', key)
                            unit = metric_conf.get('unit', '')
                        break
            
            reading_dict = dict(reading)
            reading_dict['label'] = label
            reading_dict['unit'] = unit
            latest_data_by_station[station_id][key] = reading_dict
            
    return latest_data_by_station

# --- Routes ---

@app.route('/')
def dashboard():
    config = load_config()
    enriched_data = get_enriched_data()
    
    # Prepare station info for the template
    station_tabs = []
    local_station_id = config.get('station_info', {}).get('station_id')
    
    # Ensure local station is first, then sort others
    sorted_station_ids = sorted(enriched_data.keys())
    if local_station_id in sorted_station_ids:
        sorted_station_ids.insert(0, sorted_station_ids.pop(sorted_station_ids.index(local_station_id)))

    for station_id in sorted_station_ids:
        is_local = (station_id == local_station_id)
        station_tabs.append({
            'id': station_id,
            'name': f"Station {station_id}" + (" (Local)" if is_local else " (Remote)"),
            'data': dict(sorted(enriched_data[station_id].items()))
        })

    return render_template('dashboard.html', 
                           station_name=config.get('station_info', {}).get('station_name', 'Unknown Station'),
                           station_tabs=station_tabs)

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

            # Update individual sensor enabled status and polling rates
            for sensor_id, sensor_config in current_config.get('sensors', {}).items():
                sensor_name = sensor_config['name']
                enabled_field = f"enabled_{sensor_name}"
                polling_field = f"polling_rate_{sensor_name}"
                
                current_config['sensors'][sensor_id]['enabled'] = enabled_field in request.form
                current_config['sensors'][sensor_id]['polling_rate'] = request.form.get(polling_field, type=int)

            # Update rain gauge enabled status
            if 'rain_gauge' in current_config:
                current_config['rain_gauge']['enabled'] = 'enabled_rain' in request.form

            save_config(current_config)
            flash("Configuration saved successfully! Changes will be applied on the next cycle.", "success")
        except Exception as e:
            flash(f"Error saving configuration: {e}", "danger")
            
        return redirect(url_for('settings'))

    config = load_config()
    return render_template('settings.html', config=config)

# --- API for Charts ---
@app.route('/api/historical_data')
def get_historical_data_api():
    station_id = request.args.get('station_id', type=int)
    hours = request.args.get('hours', default=24, type=int)
    
    if not station_id:
        return jsonify({"error": "station_id is required"}), 400
        
    data = db_manager.get_historical_data(station_id, hours)
    
    # Process data for charting
    processed_data = {}
    config = load_config()
    
    for row in data:
        sensor = row['sensor']
        metric = row['metric']
        
        # Find label and unit
        unit = ''
        if sensor == config.get('rain_gauge', {}).get('name'):
            unit = config['rain_gauge'].get('unit', '')
        else:
            for s_conf in config.get('sensors', {}).values():
                if s_conf.get('name') == sensor:
                    m_conf = s_conf.get('metrics', {}).get(metric)
                    if m_conf:
                        unit = m_conf.get('unit', '')
                    break
        
        key = f"{sensor}_{metric}"
        if key not in processed_data:
            processed_data[key] = {'labels': [], 'values': [], 'unit': unit}
        
        processed_data[key]['labels'].append(row['timestamp'])
        processed_data[key]['values'].append(row['value'])

    return jsonify(processed_data)


if __name__ == '__main__':
    print("--- Starting Weather Station Dashboard & API ---")
    print(f"Access the dashboard at http://127.0.0.1:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
