import sqlite3
import os
from typing import List, Optional
from src.models.schemas import UserTrigger

class DatabaseManager:
    def __init__(self, db_path: str = "bikeguard.db"):
        self.db_path = db_path
        self.initialize_db() # Changed from _init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def initialize_db(self): # Renamed from _init_db
        with sqlite3.connect(self.db_path) as conn: # Changed to use sqlite3.connect directly
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_triggers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    station_id TEXT NOT NULL,
                    threshold INTEGER DEFAULT 3,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    days_of_week TEXT DEFAULT '1,2,3,4,5',
                    is_active BOOLEAN DEFAULT 1,
                    bike_type TEXT DEFAULT 'any',
                    UNIQUE(user_id, station_id)
                )
            ''')
            
            # Simple migration: add bike_type if it doesn't exist
            try:
                cursor.execute("ALTER TABLE user_triggers ADD COLUMN bike_type TEXT DEFAULT 'any'")
                conn.commit()
            except sqlite3.OperationalError:
                # Column already exists
                pass
            
            conn.commit()

    def add_or_update_trigger(self, trigger: UserTrigger):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO user_triggers (user_id, station_id, threshold, start_time, end_time, days_of_week, is_active, bike_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, station_id) DO UPDATE SET
                    threshold=excluded.threshold,
                    start_time=excluded.start_time,
                    end_time=excluded.end_time,
                    days_of_week=excluded.days_of_week,
                    is_active=excluded.is_active,
                    bike_type=excluded.bike_type
            """, (trigger.user_id, trigger.station_id, trigger.threshold, 
                  trigger.start_time, trigger.end_time, trigger.days_of_week, trigger.is_active, trigger.bike_type))
            conn.commit()

    def get_user_triggers(self, user_id: str) -> List[dict]:
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM user_triggers WHERE user_id = ?", (user_id,))
            return [dict(row) for row in cursor.fetchall()]

    def delete_trigger(self, user_id: str, station_id: str):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM user_triggers WHERE user_id = ? AND station_id = ?", (user_id, station_id))
            conn.commit()

    def get_all_active_triggers(self) -> List[dict]:
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM user_triggers WHERE is_active = 1")
            return [dict(row) for row in cursor.fetchall()]
