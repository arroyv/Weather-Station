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
# A secret key is required for flashing messages
app.secret_key = 'super-secret-key-for-weather-station' 
config_lock = Lock()

# --- Initialize Database Manager ---
# This will be shared across all Flask requests.
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

# --- Routes ---

@app.route('/')
def dashboard():
    """
    The main dashboard page. Displays the latest sensor readings.
    """
    latest_data = db_manager.get_latest_readings()
    config = load_config()
    # Sort data for consistent display
    sorted_data = dict(sorted(latest_data.items()))
    return render_template('dashboard.html', data=sorted_data, station_name=config.get('station_info', {}).get('station_name', 'Unknown Station'))

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    """
    Allows viewing and updating the station's configuration.
    """
    if request.method == 'POST':
        try:
            current_config = load_config()
            
            # Update service toggles
            current_config['services']['adafruit_io_enabled'] = 'adafruit_io_enabled' in request.form
            current_config['services']['lora_enabled'] = 'lora_enabled' in request.form
            current_config['services']['wifi_sync_enabled'] = 'wifi_sync_enabled' in request.form
            
            # Update text fields
            current_config['station_info']['station_name'] = request.form.get('station_name', 'default-name')
            current_config['wifi_sync']['target_url'] = request.form.get('target_url', '')

            # --- NEW: Update timing intervals ---
            current_config['timing']['collection_interval_seconds'] = request.form.get('collection_interval_seconds', 600, type=int)
            current_config['timing']['transmission_interval_seconds'] = request.form.get('transmission_interval_seconds', 600, type=int)
            current_config['timing']['adafruit_io_interval_seconds'] = request.form.get('adafruit_io_interval_seconds', 300, type=int)

            save_config(current_config)
            flash("Configuration saved successfully! Changes will be applied on the next cycle.", "success")
        except Exception as e:
            flash(f"Error saving configuration: {e}", "danger")
            
        return redirect(url_for('settings'))

    config = load_config()
    return render_template('settings.html', config=config)

# --- API Endpoints (for completeness) ---

@app.route('/api/latest', methods=['GET'])
def get_latest():
    """Provides the latest data as JSON."""
    latest_data = db_manager.get_latest_readings()
    return jsonify(latest_data)

@app.route('/api/config', methods=['GET'])
def get_config():
    """Returns the current configuration as JSON."""
    return jsonify(load_config())

if __name__ == '__main__':
    print("--- Starting Weather Station Dashboard & API ---")
    print(f"Access the dashboard at http://127.0.0.1:5000")
    # Set debug=False for production use. host='0.0.0.0' makes it accessible on your network.
    app.run(host='0.0.0.0', port=5000, debug=True)
