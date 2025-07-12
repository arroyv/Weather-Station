# database.py
import sqlite3
import os
import datetime
from threading import Lock

class DatabaseManager:
    """
    Handles all interactions with the SQLite database, including creating tables,
    writing readings, and fetching data. It is thread-safe.
    """
    def __init__(self, db_path):
        self.db_path = db_path
        self._lock = Lock()
        self.conn = None
        try:
            # Ensure the directory for the database exists
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
        except (FileExistsError, FileNotFoundError):
            # The directory might already exist, or we might be in the root dir
            pass
        self.connect()
        self.create_tables()

    def connect(self):
        """Establishes a connection to the SQLite database file."""
        try:
            # `check_same_thread=False` is important for multi-threaded access
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            # Use the Row factory to access columns by name
            self.conn.row_factory = sqlite3.Row
            print(f"[Database] Connected to {self.db_path}")
        except sqlite3.Error as e:
            print(f"[Database] ERROR: Could not connect to database: {e}")
            raise

    def close(self):
        """Closes the database connection."""
        if self.conn:
            self.conn.close()
            print(f"[Database] Disconnected from {self.db_path}")

    def create_tables(self):
        """Creates the necessary tables if they don't already exist."""
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
        """Writes a single sensor reading to the database."""
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
        """
        Retrieves the most recent reading for each sensor/metric combination,
        grouped by station ID.
        """
        with self._lock:
            try:
                cursor = self.conn.cursor()
                # This query efficiently gets the full row for the latest timestamp
                # for each unique combination of station, sensor, and metric.
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
                    # Create a unique key for the dashboard (e.g., 'soil-temp-c')
                    key = f"{row['sensor']}-{row['metric']}"
                    data_by_station[station_id][key] = dict(row)
                return data_by_station
            except sqlite3.Error as e:
                print(f"[Database] ERROR: Could not fetch latest readings: {e}")
                return {}

    def get_historical_data(self, station_id, sensor, metric, hours):
        """
        Retrieves historical data for a specific sensor and metric over a
        given number of hours.
        """
        with self._lock:
            try:
                cursor = self.conn.cursor()
                # Query for data within the specified time window
                query = """
                    SELECT timestamp, value FROM readings 
                    WHERE station_id = ? AND sensor = ? AND metric = ? AND timestamp >= datetime('now', '-' || ? || ' hours') 
                    ORDER BY timestamp ASC
                """
                cursor.execute(query, (station_id, sensor, metric, hours))
                return [dict(row) for row in cursor.fetchall()]
            except sqlite3.Error as e:
                print(f"[Database] ERROR: Could not fetch historical data: {e}")
                return []

    def get_unsent_lora_data(self, station_id, last_sent_id, limit=10):
        """
        Retrieves a batch of readings that have not yet been sent via LoRa.
        """
        with self._lock:
            try:
                cursor = self.conn.cursor()
                query = "SELECT * FROM readings WHERE station_id = ? AND id > ? ORDER BY id ASC LIMIT ?"
                cursor.execute(query, (station_id, last_sent_id, limit))
                return [dict(row) for row in cursor.fetchall()]
            except sqlite3.Error as e:
                print(f"[Database] ERROR: Could not fetch unsent LoRa data: {e}")
                return []
