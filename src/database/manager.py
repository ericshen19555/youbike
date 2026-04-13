import sqlite3
import logging
import os
from typing import List, Optional
from datetime import datetime
from src.models.schemas import UserSubscription, ActiveTask, StationInfo

class DatabaseManager:
    def __init__(self, db_path: str = "bikeguard.db"):
        self.db_path = db_path
        self.initialize_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def initialize_db(self):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            # 1. User Long-term Subscriptions
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    station_id TEXT NOT NULL,
                    rrule TEXT NOT NULL,
                    threshold INTEGER DEFAULT 3,
                    bike_type TEXT DEFAULT 'any',
                    is_active BOOLEAN DEFAULT 1,
                    UNIQUE(user_id, station_id, rrule)
                )
            ''')
            
            # Migration: Check if we need to update the unique constraint
            # (If the old UNIQUE(user_id, station_id) still exists)
            cursor.execute("PRAGMA table_info(user_subscriptions)")
            columns = cursor.fetchall()
            # If we need to migrate, we'll know by checking index info
            cursor.execute("PRAGMA index_list(user_subscriptions)")
            indexes = cursor.fetchall()
            need_migration = False
            for idx in indexes:
                # If there's an index that only covers user_id and station_id, but not rrule
                cursor.execute(f"PRAGMA index_info('{idx['name']}')")
                info = cursor.fetchall()
                col_names = [i[2] for i in info]
                if set(col_names) == {'user_id', 'station_id'}:
                    need_migration = True
                    logging.info("Database migration: Detected legacy subscription schema. Migrating to RRule-based unique index...")
                    break
            
            if need_migration:
                # SQLite doesn't support DROP CONSTRAINT, so we recreate the table
                cursor.execute("ALTER TABLE user_subscriptions RENAME TO user_subscriptions_old")
                cursor.execute('''
                    CREATE TABLE user_subscriptions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        station_id TEXT NOT NULL,
                        rrule TEXT NOT NULL,
                        threshold INTEGER DEFAULT 3,
                        bike_type TEXT DEFAULT 'any',
                        is_active BOOLEAN DEFAULT 1,
                        UNIQUE(user_id, station_id, rrule)
                    )
                ''')
                cursor.execute('''
                    INSERT INTO user_subscriptions (id, user_id, station_id, rrule, threshold, bike_type, is_active)
                    SELECT id, user_id, station_id, rrule, threshold, bike_type, is_active FROM user_subscriptions_old
                ''')
                cursor.execute("DROP TABLE user_subscriptions_old")
            
            # 2. Worker Active Task Queue
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS active_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sub_id INTEGER NOT NULL,
                    next_run TEXT NOT NULL,
                    current_interval INTEGER DEFAULT 60,
                    status TEXT DEFAULT 'pending',
                    last_notified_at TEXT,
                    target_time TEXT,
                    FOREIGN KEY (sub_id) REFERENCES user_subscriptions(id)
                )
            ''')
            
            # Migration for active_tasks: check if columns exist
            cursor.execute("PRAGMA table_info(active_tasks)")
            task_cols = cursor.fetchall()
            col_names = [col[1] for col in task_cols]
            
            if 'last_notified_at' not in col_names:
                logging.info("Database migration: Adding 'last_notified_at' column to 'active_tasks' table.")
                cursor.execute("ALTER TABLE active_tasks ADD COLUMN last_notified_at TEXT")
                
            if 'target_time' not in col_names:
                logging.info("Database migration: Adding 'target_time' column to 'active_tasks' table.")
                cursor.execute("ALTER TABLE active_tasks ADD COLUMN target_time TEXT")

            # 3. Station Metadata Cache
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS stations (
                    sno TEXT PRIMARY KEY,
                    sna TEXT NOT NULL,
                    tot INTEGER,
                    lat REAL,
                    lng REAL,
                    ar TEXT,
                    sarea TEXT,
                    sareaen TEXT,
                    updatetime TEXT,
                    act TEXT DEFAULT '1'
                )
            ''')

            # 4. System Metadata
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS system_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')
            conn.commit()
        finally:
            conn.close()

    # --- Subscription Methods ---
    def add_or_update_subscription(self, sub: UserSubscription) -> Optional[int]:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO user_subscriptions (user_id, station_id, rrule, threshold, bike_type, is_active)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, station_id, rrule) DO UPDATE SET
                    threshold=excluded.threshold,
                    bike_type=excluded.bike_type,
                    is_active=excluded.is_active
                RETURNING id
            """, (sub.user_id, sub.station_id, sub.rrule, sub.threshold, sub.bike_type, sub.is_active))
            result = cursor.fetchone()
            conn.commit()
            return result[0] if result else None
        finally:
            conn.close()

    def get_user_subscriptions(self, user_id: str) -> List[dict]:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM user_subscriptions WHERE user_id = ?", (user_id,))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_user_station_subscriptions(self, user_id: str, station_id: str) -> List[dict]:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM user_subscriptions WHERE user_id = ? AND station_id = ?", (user_id, station_id))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_all_active_subscriptions(self) -> List[dict]:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM user_subscriptions WHERE is_active = 1")
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    # --- Task Queue Methods ---
    def add_task(self, task: ActiveTask):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO active_tasks (sub_id, next_run, current_interval, status, target_time)
                VALUES (?, ?, ?, ?, ?)
            """, (task.sub_id, task.next_run, task.current_interval, task.status, task.target_time))
            conn.commit()
        finally:
            conn.close()

    def get_pending_tasks(self, current_time_iso: str) -> List[dict]:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT t.*, s.user_id, s.station_id, s.threshold, s.bike_type, s.rrule
                FROM active_tasks t
                JOIN user_subscriptions s ON t.sub_id = s.id
                WHERE t.status = 'pending' AND t.next_run <= ?
            """, (current_time_iso,))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def update_task_status(self, task_id: int, status: str, next_run: Optional[str] = None, interval: Optional[int] = None, last_notified_at: Optional[str] = None):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if next_run and interval:
                if last_notified_at:
                    cursor.execute("UPDATE active_tasks SET status = ?, next_run = ?, current_interval = ?, last_notified_at = ? WHERE id = ?", 
                                 (status, next_run, interval, last_notified_at, task_id))
                else:
                    cursor.execute("UPDATE active_tasks SET status = ?, next_run = ?, current_interval = ? WHERE id = ?", 
                                 (status, next_run, interval, task_id))
            elif last_notified_at:
                cursor.execute("UPDATE active_tasks SET status = ?, last_notified_at = ? WHERE id = ?", (status, last_notified_at, task_id))
            else:
                cursor.execute("UPDATE active_tasks SET status = ? WHERE id = ?", (status, task_id))
            conn.commit()
        finally:
            conn.close()

    def delete_completed_tasks(self):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM active_tasks WHERE status = 'completed'")
            conn.commit()
        finally:
            conn.close()

    def get_tasks_for_subscription(self, sub_id: int, status: Optional[str] = None) -> List[dict]:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if status:
                cursor.execute("SELECT * FROM active_tasks WHERE sub_id = ? AND status = ?", (sub_id, status))
            else:
                cursor.execute("SELECT * FROM active_tasks WHERE sub_id = ?", (sub_id,))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def delete_subscription(self, user_id: str, station_id: str):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM active_tasks 
                WHERE sub_id IN (SELECT id FROM user_subscriptions WHERE user_id = ? AND station_id = ?)
            """, (user_id, station_id))
            cursor.execute("DELETE FROM user_subscriptions WHERE user_id = ? AND station_id = ?", (user_id, station_id))
            conn.commit()
        finally:
            conn.close()

    def delete_subscription_by_id(self, sub_id: int):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM active_tasks WHERE sub_id = ?", (sub_id,))
            cursor.execute("DELETE FROM user_subscriptions WHERE id = ?", (sub_id,))
            conn.commit()
        finally:
            conn.close()

    def delete_all_user_subscriptions(self, user_id: str):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM active_tasks 
                WHERE sub_id IN (SELECT id FROM user_subscriptions WHERE user_id = ?)
            """, (user_id,))
            cursor.execute("DELETE FROM user_subscriptions WHERE user_id = ?", (user_id,))
            conn.commit()
        finally:
            conn.close()

    # --- Station Metadata Methods ---
    def save_stations(self, stations: List[StationInfo]):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            for s in stations:
                cursor.execute("""
                    INSERT INTO stations (sno, sna, tot, lat, lng, ar, sarea, sareaen, updatetime, act)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(sno) DO UPDATE SET
                        sna=excluded.sna, tot=excluded.tot, lat=excluded.lat, lng=excluded.lng,
                        ar=excluded.ar, sarea=excluded.sarea, sareaen=excluded.sareaen,
                        updatetime=excluded.updatetime, act=excluded.act
                """, (s.sno, s.sna, s.tot, s.lat, s.lng, s.ar, s.sarea, s.sareaen, s.updatetime, s.act))
            conn.commit()
        finally:
            conn.close()

    def get_stations(self) -> List[StationInfo]:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM stations")
            rows = cursor.fetchall()
            return [StationInfo(**dict(row)) for row in rows]
        finally:
            conn.close()

    # --- System Meta Methods ---
    def get_meta(self, key: str) -> Optional[str]:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM system_meta WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    def set_meta(self, key: str, value: str):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO system_meta (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """, (key, value))
            conn.commit()
        finally:
            conn.close()
