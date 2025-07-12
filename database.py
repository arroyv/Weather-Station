# database.py
import sqlite3
import os
import datetime
from threading import Lock

class DatabaseManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self._lock = Lock()
        self.conn = None
        try:
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
        except FileExistsError:
            pass
        self.connect()
        self.create_tables()

    def connect(self):
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            print(f"[Database] Connected to {self.db_path}")
        except sqlite3.Error as e:
            print(f"[Database] ERROR: Could not connect to database: {e}")
            raise

    def close(self):
        if self.conn:
            self.conn.close()

    def create_tables(self):
        with self._lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS readings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        station_id INTEGER NOT NULL,
                        sensor TEXT NOT NULL,
                        metric TEXT NOT NULL,
                        value REAL NOT NULL,
                        rssi REAL
                    )
                ''')
                self.conn.commit()
            except sqlite3.Error as e:
                print(f"[Database] ERROR: Could not create tables: {e}")

    def write_reading(self, station_id, sensor, metric, value, rssi=None, timestamp=None):
        ts = timestamp if timestamp else datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute(
                    "INSERT INTO readings (timestamp, station_id, sensor, metric, value, rssi) VALUES (?, ?, ?, ?, ?, ?)",
                    (ts, station_id, sensor, metric, value, rssi)
                )
                self.conn.commit()
                return cursor.lastrowid
            except sqlite3.Error as e:
                print(f"[Database] ERROR: Failed to write reading: {e}")
                return None

    def get_latest_readings_by_station(self):
        with self._lock:
            try:
                cursor = self.conn.cursor()
                query = """
                    SELECT r.* FROM readings r
                    INNER JOIN (
                        SELECT station_id, sensor, metric, MAX(timestamp) AS max_ts
                        FROM readings
                        GROUP BY station_id, sensor, metric
                    ) AS latest ON r.station_id = latest.station_id
                               AND r.sensor = latest.sensor
                               AND r.metric = latest.metric
                               AND r.timestamp = latest.max_ts;
                """
                cursor.execute(query)
                rows = cursor.fetchall()
                data_by_station = {}
                for row in rows:
                    station_id = row['station_id']
                    if station_id not in data_by_station:
                        data_by_station[station_id] = {}
                    key = f"{row['sensor']}-{row['metric']}"
                    data_by_station[station_id][key] = dict(row)
                return data_by_station
            except sqlite3.Error as e:
                print(f"[Database] ERROR: Could not fetch latest readings: {e}")
                return {}

    def get_historical_data(self, station_id, hours, metric_column):
        # This method needs to be adapted for the "long" format.
        # The metric_column is now a combination of sensor and metric.
        sensor_name, metric_name = metric_column.split('_', 1)
        metric_name = metric_name.replace('_', '-')
        
        with self._lock:
            try:
                cursor = self.conn.cursor()
                query = """
                    SELECT timestamp, value FROM readings 
                    WHERE station_id = ? AND sensor = ? AND metric = ? AND timestamp >= datetime('now', '-' || ? || ' hours') 
                    ORDER BY timestamp ASC
                """
                cursor.execute(query, (station_id, sensor_name, metric_name, hours))
                return [dict(row) for row in cursor.fetchall()]
            except sqlite3.Error as e:
                print(f"[Database] ERROR: Could not fetch historical data: {e}")
                return []

    def get_unsent_lora_data(self, station_id, last_sent_id, limit=3):
        with self._lock:
            try:
                cursor = self.conn.cursor()
                query = "SELECT * FROM readings WHERE station_id = ? AND id > ? ORDER BY id ASC LIMIT ?"
                cursor.execute(query, (station_id, last_sent_id, limit))
                return cursor.fetchall()
            except sqlite3.Error as e:
                print(f"[Database] ERROR: Could not fetch unsent LoRa data: {e}")
                return []