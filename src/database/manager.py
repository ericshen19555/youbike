import sqlite3
import os
from typing import List, Optional
from src.models.schemas import UserSubscription, ActiveTask

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
                    UNIQUE(user_id, station_id)
                )
            ''')
            
            # 2. Worker Active Task Queue
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS active_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sub_id INTEGER NOT NULL,
                    next_run TEXT NOT NULL,
                    current_interval INTEGER DEFAULT 60,
                    status TEXT DEFAULT 'pending',
                    FOREIGN KEY (sub_id) REFERENCES user_subscriptions(id)
                )
            ''')
            conn.commit()
        finally:
            conn.close()

    # --- Subscription Methods ---
    def add_or_update_subscription(self, sub: UserSubscription) -> int:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO user_subscriptions (user_id, station_id, rrule, threshold, bike_type, is_active)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, station_id) DO UPDATE SET
                    rrule=excluded.rrule,
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
                INSERT INTO active_tasks (sub_id, next_run, current_interval, status)
                VALUES (?, ?, ?, ?)
            """, (task.sub_id, task.next_run, task.current_interval, task.status))
            conn.commit()
        finally:
            conn.close()

    def get_pending_tasks(self, current_time_iso: str) -> List[dict]:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT t.*, s.user_id, s.station_id, s.threshold, s.bike_type 
                FROM active_tasks t
                JOIN user_subscriptions s ON t.sub_id = s.id
                WHERE t.status = 'pending' AND t.next_run <= ?
            """, (current_time_iso,))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def update_task_status(self, task_id: int, status: str, next_run: Optional[str] = None, interval: Optional[int] = None):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if next_run and interval:
                cursor.execute("UPDATE active_tasks SET status = ?, next_run = ?, current_interval = ? WHERE id = ?", 
                             (status, next_run, interval, task_id))
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

    def delete_subscription(self, user_id: str, station_id: str):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            # 1. Delete associated tasks first
            cursor.execute("""
                DELETE FROM active_tasks 
                WHERE sub_id IN (SELECT id FROM user_subscriptions WHERE user_id = ? AND station_id = ?)
            """, (user_id, station_id))
            # 2. Delete subscription
            cursor.execute("DELETE FROM user_subscriptions WHERE user_id = ? AND station_id = ?", (user_id, station_id))
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



