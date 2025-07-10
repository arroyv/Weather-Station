# database.py
import sqlite3
import os
import datetime
from threading import Lock

class DatabaseManager:
    """
    Handles all interactions with the SQLite database.
    This is the single source of truth for all weather data.
    """
    def __init__(self, db_path):
        self.db_path = db_path
        self._lock = Lock()
        self.conn = None
        # Ensure the directory for the database exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.connect()
        self.create_tables()

    def connect(self):
        """Establishes a connection to the database."""
        try:
            # check_same_thread=False is needed because the Flask app and the collector will access this from different threads.
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            print(f"[Database] Connected to {self.db_path}")
        except sqlite3.Error as e:
            print(f"[Database] ERROR: Could not connect to database: {e}")
            raise

    def create_tables(self):
        """Creates the necessary tables if they don't already exist."""
        with self._lock:
            try:
                cursor = self.conn.cursor()
                # The readings table is the core of the system.
                # - id: A unique, auto-incrementing key to ensure data order.
                # - timestamp: When the reading was recorded (UTC).
                # - station_id: Which station generated the data (from config).
                # - sensor, metric, value: The actual data.
                # - rssi: Signal strength if data came via LoRa.
                # - is_synced: A flag to track if data has been sent to a central server (Jetson Nano).
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS readings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        station_id INTEGER NOT NULL,
                        sensor TEXT NOT NULL,
                        metric TEXT NOT NULL,
                        value REAL NOT NULL,
                        rssi REAL,
                        is_synced INTEGER DEFAULT 0
                    )
                ''')
                self.conn.commit()
                print("[Database] Tables created or already exist.")
            except sqlite3.Error as e:
                print(f"[Database] ERROR: Could not create tables: {e}")

    def write_reading(self, station_id, sensor, metric, value, rssi=None):
        """Writes a single sensor reading to the database."""
        ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
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

    def get_latest_readings(self):
        """
        Retrieves the most recent reading for each sensor/metric combination.
        This is used by the dashboard.
        """
        with self._lock:
            try:
                cursor = self.conn.cursor()
                # This query finds the max timestamp for each sensor/metric and then joins back to get the full row.
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
                # Convert rows to a more usable dictionary format
                latest_data = {}
                for row in rows:
                    key = f"{row['sensor']}-{row['metric']} (Station {row['station_id']})"
                    latest_data[key] = dict(row)
                return latest_data
            except sqlite3.Error as e:
                print(f"[Database] ERROR: Could not fetch latest readings: {e}")
                return {}

    def get_unsynced_data(self, limit=50):
        """
        Retrieves a batch of data that has not yet been synced over WiFi.
        """
        with self._lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("SELECT * FROM readings WHERE is_synced = 0 ORDER BY id ASC LIMIT ?", (limit,))
                return cursor.fetchall()
            except sqlite3.Error as e:
                print(f"[Database] ERROR: Could not fetch unsynced data: {e}")
                return []

    def mark_data_as_synced(self, record_ids):
        """Marks a list of record IDs as synced."""
        if not record_ids:
            return
        with self._lock:
            try:
                cursor = self.conn.cursor()
                # The IN clause is perfect for updating multiple specific rows
                placeholders = ', '.join('?' for _ in record_ids)
                query = f"UPDATE readings SET is_synced = 1 WHERE id IN ({placeholders})"
                cursor.execute(query, record_ids)
                self.conn.commit()
            except sqlite3.Error as e:
                print(f"[Database] ERROR: Could not mark data as synced: {e}")

    def close(self):
        """Closes the database connection."""
        if self.conn:
            self.conn.close()
            print("[Database] Connection closed.")
