# web_api.py

import os
import sqlite3
import json
from flask import Flask, jsonify, request
from threading import Lock

# --- Configuration ---
project_dir = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(project_dir, 'weather_data.db')
CONFIG_PATH = os.path.join(project_dir, 'config.json')

app = Flask(__name__)
config_lock = Lock()

def query_db(query, args=(), one=False):
    """Helper function to safely query the database in read-only mode."""
    try:
        # Connect in read-only mode to prevent accidental writes from the API
        con = sqlite3.connect(f'file:{DB_PATH}?mode=ro', uri=True)
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute(query, args)
        rv = cur.fetchall()
        con.close()
        return (rv[0] if rv else None) if one else rv
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return None

@app.route('/')
def index():
    """A simple status page to show the API is running."""
    return "<h1>Weather Station API</h1><p>API is running. Use endpoints like /api/config or /api/history.</p>"

@app.route('/api/history', methods=['GET'])
def get_history():
    """Provides historical data. Example: /api/history?sensor=soil&metric=temperature&hours=24"""
    sensor = request.args.get('sensor')
    metric = request.args.get('metric')
    hours = request.args.get('hours', default=24, type=int)
    if not sensor or not metric:
        return jsonify({"error": "Missing 'sensor' and 'metric' parameters"}), 400
    
    query_str = "SELECT timestamp, value FROM readings WHERE sensor = ? AND metric = ? AND timestamp >= datetime('now', '-' || ? || ' hours') ORDER BY timestamp ASC"
    results = query_db(query_str, args=(sensor, metric, hours))
    
    if results is None:
        return jsonify({"error": "Database query failed. Is the collector service running and creating data?"}), 500
    
    data = [dict(row) for row in results]
    return jsonify(data)

@app.route('/api/config', methods=['GET'])
def get_config():
    """Reads and returns the current configuration."""
    with config_lock:
        with open(CONFIG_PATH, 'r') as f:
            config_data = json.load(f)
    return jsonify(config_data)

@app.route('/api/config', methods=['POST'])
def set_config():
    """Receives new config data (as JSON) and saves it."""
    new_config = request.json
    if not new_config:
        return jsonify({"error": "Invalid JSON payload"}), 400
    
    with config_lock:
        # It's safer to read the old config, update it, and then write
        # This prevents accidental deletion of keys if the payload is partial.
        try:
            with open(CONFIG_PATH, 'r') as f:
                current_config = json.load(f)
            current_config.update(new_config)
            with open(CONFIG_PATH, 'w') as f:
                json.dump(current_config, f, indent=2)
        except Exception as e:
            return jsonify({"error": f"Failed to write config file: {e}"}), 500
            
    return jsonify({"success": True, "message": "Configuration saved. Collector will reload settings automatically."})

if __name__ == '__main__':
    print("--- Starting Weather Station API Service ---")
    print(f"View status at http://127.0.0.1:5000")
    # Set debug=False for production use
    app.run(host='0.0.0.0', port=5000, debug=True)