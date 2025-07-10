import sqlite3
from flask import Flask, render_template, jsonify, g

app = Flask(__name__)
DATABASE = 'path to the db file'

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
    return g.db

@app.teardown_appcontext
def close_connection(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()

@app.route('/')
def main():
    return render_template('index.html')


@app.route('/monthly-stats')
def monthly_stats():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT month,
               AVG(CO2) AS avg_co2,
               AVG("Atmospheric Pressure") AS avg_pressure,
               AVG("Wind Speed") AS avg_wind_speed,
               AVG("Wind Direction") AS avg_wind_direction
        FROM sensor_data
        GROUP BY month
        ORDER BY month
    """)
    rows = cur.fetchall()

    months = []
    co2_avgs = []
    pressure_avgs = []
    wind_speed_avgs = []
    wind_direction_avgs = []

    for row in rows:
        months.append(row[0])
        co2_avgs.append(row[1])
        pressure_avgs.append(row[2])
        wind_speed_avgs.append(row[3])
        wind_direction_avgs.append(row[4])
    return jsonify({
        'months': months,
        'CO2': co2_avgs,
        'Atmospheric Pressure': pressure_avgs,
        'Wind Speed': wind_speed_avgs,
        'Wind Direction': wind_direction_avgs,
    })
@app.route('/latest-data', methods=['GET'])
def latest_data():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT CO2, "Atmospheric Pressure", "Wind Speed", "Wind Direction"
        FROM sensor_data
        ORDER BY RANDOM()
        LIMIT 1
    """)
    row = cur.fetchone()

    if row:
        co2, pressure, wind_speed, wind_direction = row
        return jsonify({
            'CO2': co2,
            'Atmospheric Pressure': pressure,
            'Wind Speed': wind_speed,
            'Wind Direction': wind_direction
        })
    else:
        return jsonify({'error': 'No data found'}), 404

if __name__ == '__main__':
    app.run(host="0.0.0.0",debug=True)
