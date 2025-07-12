# database.py
import sqlite3
import os
import datetime
from threading import Lock

class DatabaseManager:
    """
    Handles all interactions with the SQLite database using a "wide" table format,
    dynamically building the schema from the configuration file.
    """
    def __init__(self, db_path, config):
        self.db_path = db_path
        self._lock = Lock()
        self.conn = None
        self.config = config
        # Generate the column schema from the config
        self.db_columns = self._get_columns_from_config()
        
        try:
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
        except FileExistsError:
            pass
        self.connect()
        self.create_table()

    def _get_columns_from_config(self):
        """Builds a list of database column names and types from the config."""
        columns = []
        # Add columns for Modbus sensors
        for s_conf in self.config.get('sensors', {}).values():
            for metric in s_conf.get('metrics', {}).keys():
                # Sanitize metric name for SQL column name
                col_name = f"{s_conf['name']}_{metric.replace('-', '_')}"
                columns.append(f"{col_name} REAL")
        
        # Add column for Rain Gauge
        rg_conf = self.config.get('rain_gauge', {})
        if rg_conf and rg_conf.get('enabled'):
            col_name = f"{rg_conf['name']}_{rg_conf['metric']}"
            columns.append(f"{col_name} REAL")
            
        # Add column for LoRa signal strength
        columns.append("rssi REAL")
        return sorted(list(set(columns))) # Sort for consistent column order

    def connect(self):
        """Establishes a connection to the database."""
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            print(f"[Database] Connected to {self.db_path}")
        except sqlite3.Error as e:
            print(f"[Database] ERROR: Could not connect to database: {e}")
            raise

    def close(self):
        """Closes the database connection."""
        if self.conn:
            self.conn.close()
            # print(f"[Database] Closed connection to {self.db_path}")

    def create_table(self):
        """Creates a single 'snapshots' table with a column for each sensor metric."""
        with self._lock:
            try:
                cursor = self.conn.cursor()
                columns_sql = ",\n".join(self.db_columns)
                query = f"""
                    CREATE TABLE IF NOT EXISTS snapshots (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        station_id INTEGER NOT NULL,
                        {columns_sql}
                    )
                """
                cursor.execute(query)
                self.conn.commit()
            except sqlite3.Error as e:
                print(f"[Database] ERROR: Could not create table: {e}")

    def write_snapshot(self, station_id, snapshot_data):
        """Writes a full row of sensor data to the snapshots table."""
        with self._lock:
            try:
                column_names = [col.split()[0] for col in self.db_columns]
                columns_for_sql = ['timestamp', 'station_id'] + column_names
                placeholders = ', '.join(['?'] * len(columns_for_sql))
                
                values = [datetime.datetime.now(datetime.timezone.utc).isoformat(), station_id]
                for col_name in column_names:
                    values.append(snapshot_data.get(col_name))

                cursor = self.conn.cursor()
                cursor.execute(
                    f"INSERT INTO snapshots ({', '.join(columns_for_sql)}) VALUES ({placeholders})",
                    tuple(values)
                )
                self.conn.commit()
                return cursor.lastrowid
            except sqlite3.Error as e:
                print(f"[Database] ERROR: Failed to write snapshot: {e}")
                return None

    def get_latest_snapshot(self, station_id):
        """Retrieves the most recent snapshot for a given station."""
        with self._lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("SELECT * FROM snapshots WHERE station_id = ? ORDER BY timestamp DESC LIMIT 1", (station_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
            except sqlite3.Error as e:
                print(f"[Database] ERROR: Could not fetch latest snapshot: {e}")
                return None

    def get_historical_data(self, station_id, hours, metric_column):
        """Retrieves historical data for a specific metric column."""
        valid_columns = [col.split()[0] for col in self.db_columns]
        if metric_column not in valid_columns:
            raise ValueError(f"Invalid metric column requested: {metric_column}")

        with self._lock:
            try:
                cursor = self.conn.cursor()
                query = f"""
                    SELECT timestamp, {metric_column} as value FROM snapshots
                    WHERE station_id = ? AND timestamp >= datetime('now', '-' || ? || ' hours')
                    ORDER BY timestamp ASC
                """
                cursor.execute(query, (station_id, hours))
                # Fetch all and convert to list of dicts to ensure connection is not needed later
                return [dict(row) for row in cursor.fetchall()]
            except sqlite3.Error as e:
                print(f"[Database] ERROR: Could not fetch historical data: {e}")
                return []

    def get_unsent_snapshot(self, station_id, last_sent_id):
        """Retrieves the latest snapshot that has not yet been sent."""
        with self._lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("SELECT * FROM snapshots WHERE station_id = ? AND id > ? ORDER BY id DESC LIMIT 1", (station_id, last_sent_id))
                row = cursor.fetchone()
                return dict(row) if row else None
            except sqlite3.Error as e:
                print(f"[Database] ERROR: Could not fetch unsent snapshot: {e}")
                return None