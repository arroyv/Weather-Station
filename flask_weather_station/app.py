from flask import Flask, render_template, request, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit
import random
import eventlet
import threading
from datetime import datetime, timedelta

eventlet.monkey_patch()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sensors.db'
db = SQLAlchemy(app)
socketio = SocketIO(app, async_mode='eventlet')

class SensorData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sensor_name = db.Column(db.String(50), nullable=False)
    value = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    direction = db.Column(db.Integer, nullable=True)  # Adding direction column

def generate_random_data():
    sensors = ['pressure', 'temperature', 'co2', 'light_intensity', 'humidity', 'wind_speed']
    directions = ["North", "Northeast", "East", "Southeast", "South", "Southwest", "West", "Northwest"]
    while True:
        with app.app_context():
            data = {}
            for sensor in sensors:
                if sensor == 'pressure':
                    value = random.uniform(90, 110)  # Example range for pressure in kPa
                elif sensor == 'temperature':
                    value = random.uniform(-10, 40)  # Example range for temperature in Celsius
                elif sensor == 'co2':
                    value = random.uniform(300, 600)  # Example range for CO2 concentration in ppm
                elif sensor == 'light_intensity':
                    value = random.uniform(0, 1000)  # Example range for light intensity in Lux
                elif sensor == 'humidity':
                    value = random.uniform(0, 100)  # Example range for humidity in %RH
                elif sensor == 'wind_speed':
                    value = random.uniform(0, 30)  # Example range for wind speed in m/s
                    direction = random.choice(range(0, 8))  # Example range for direction position
                    str_dir = directions[direction]

                data[sensor] = value
                direction_data = direction if sensor == 'wind_speed' else None

                sensor_data = SensorData(sensor_name=sensor, value=value, direction=direction_data)
                db.session.add(sensor_data)
                if sensor == 'wind_speed':
                    socketio.emit('new_data', {'sensor_name': sensor, 'value': value, 'direction': str_dir})
                else:
                    socketio.emit('new_data', {'sensor_name': sensor, 'value': value})
            db.session.commit()
        socketio.sleep(20)  # Generate data every 20 seconds

@app.route('/')
def index():
    sensors = ['pressure', 'temperature', 'co2', 'light_intensity', 'humidity', 'wind_speed']
    initial_data = {}
    for sensor in sensors:
        latest_data = SensorData.query.filter_by(sensor_name=sensor).order_by(SensorData.timestamp.desc()).first()
        if latest_data:
            initial_value = latest_data.value
            initial_direction = latest_data.direction
            direction_label = None
            if sensor == 'wind_speed' and initial_direction is not None:
                directions = ["North", "Northeast", "East", "Southeast", "South", "Southwest", "West", "Northwest"]
                direction_label = directions[int(initial_direction)]
            initial_data[sensor] = {'value': initial_value, 'direction': direction_label}
        else:
            initial_data[sensor] = {'value': 'N/A', 'direction': 'N/A'}
    response = make_response(render_template('index.html', initial_data=initial_data))
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response

@app.route('/sensor_data/<sensor_name>')
def sensor_data(sensor_name):
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=365*10)  # Default to 10 years for all-time data
    time_range = request.args.get('range', 'all')
    
    if time_range == 'day':
        start_time = end_time - timedelta(days=1)
    elif time_range == 'week':
        start_time = end_time - timedelta(weeks=1)
    elif time_range == 'month':
        start_time = end_time - timedelta(days=30)
    elif time_range == 'year':
        start_time = end_time - timedelta(days=365)
    
    data = SensorData.query.filter(SensorData.sensor_name == sensor_name, SensorData.timestamp >= start_time).all()
    data_points = [{'timestamp': d.timestamp, 'value': d.value, 'direction': d.direction} for d in data if sensor_name == 'wind_speed']
    data_points += [{'timestamp': d.timestamp, 'value': d.value} for d in data if sensor_name != 'wind_speed']
    return jsonify(data_points)

@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

def create_db():
    with app.app_context():
        db.create_all()

if __name__ == '__main__':
    create_db()
    threading.Thread(target=generate_random_data).start()
    socketio.run(app, host='0.0.0.0', port=5001, debug=False)
