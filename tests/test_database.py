"""Tests for src/database/manager.py — full CRUD + migration logic."""
import sqlite3
from src.database.manager import DatabaseManager
from src.models.schemas import UserSubscription, ActiveTask, StationInfo


class TestDatabaseManagerInit:
    def test_initialize_creates_tables(self, tmp_db):
        conn = sqlite3.connect(tmp_db.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row['name'] for row in cursor.fetchall()}
        conn.close()
        assert 'user_subscriptions' in tables
        assert 'active_tasks' in tables
        assert 'stations' in tables
        assert 'system_meta' in tables

    def test_migration_from_old_unique_constraint(self, tmp_path):
        """Simulate old schema with UNIQUE(user_id, station_id) and verify migration."""
        db_path = str(tmp_path / "old.db")
        conn = sqlite3.connect(db_path)
        conn.execute('''
            CREATE TABLE user_subscriptions (
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
        conn.execute("INSERT INTO user_subscriptions (user_id, station_id, rrule) VALUES ('u1','s1','FREQ=DAILY')")
        conn.commit()
        conn.close()

        dm = DatabaseManager(db_path)
        dm.initialize_db()

        # After migration, should be able to insert same user+station with different rrule
        sub1 = UserSubscription(user_id="u1", station_id="s1", rrule="FREQ=WEEKLY")
        dm.add_or_update_subscription(sub1)
        subs = dm.get_user_subscriptions("u1")
        assert len(subs) == 2  # old DAILY + new WEEKLY


class TestSubscriptionCRUD:
    def test_add_subscription(self, tmp_db):
        sub = UserSubscription(user_id="u1", station_id="s1", rrule="FREQ=DAILY")
        sub_id = tmp_db.add_or_update_subscription(sub)
        assert sub_id is not None

    def test_get_user_subscriptions(self, tmp_db):
        sub = UserSubscription(user_id="u1", station_id="s1", rrule="FREQ=DAILY")
        tmp_db.add_or_update_subscription(sub)
        subs = tmp_db.get_user_subscriptions("u1")
        assert len(subs) == 1
        assert subs[0]['station_id'] == "s1"

    def test_upsert_same_rrule_updates(self, tmp_db):
        sub1 = UserSubscription(user_id="u1", station_id="s1", rrule="FREQ=DAILY", threshold=3)
        tmp_db.add_or_update_subscription(sub1)
        sub2 = UserSubscription(user_id="u1", station_id="s1", rrule="FREQ=DAILY", threshold=10)
        tmp_db.add_or_update_subscription(sub2)
        subs = tmp_db.get_user_subscriptions("u1")
        assert len(subs) == 1
        assert subs[0]['threshold'] == 10

    def test_different_rrule_creates_new(self, tmp_db):
        sub1 = UserSubscription(user_id="u1", station_id="s1", rrule="FREQ=DAILY")
        sub2 = UserSubscription(user_id="u1", station_id="s1", rrule="FREQ=WEEKLY")
        tmp_db.add_or_update_subscription(sub1)
        tmp_db.add_or_update_subscription(sub2)
        subs = tmp_db.get_user_subscriptions("u1")
        assert len(subs) == 2

    def test_get_user_station_subscriptions(self, tmp_db):
        sub1 = UserSubscription(user_id="u1", station_id="s1", rrule="FREQ=DAILY")
        sub2 = UserSubscription(user_id="u1", station_id="s1", rrule="FREQ=WEEKLY")
        sub3 = UserSubscription(user_id="u1", station_id="s2", rrule="FREQ=DAILY")
        tmp_db.add_or_update_subscription(sub1)
        tmp_db.add_or_update_subscription(sub2)
        tmp_db.add_or_update_subscription(sub3)
        subs = tmp_db.get_user_station_subscriptions("u1", "s1")
        assert len(subs) == 2

    def test_get_all_active_subscriptions(self, tmp_db):
        sub = UserSubscription(user_id="u1", station_id="s1", rrule="FREQ=DAILY")
        tmp_db.add_or_update_subscription(sub)
        active = tmp_db.get_all_active_subscriptions()
        assert len(active) == 1

    def test_delete_subscription(self, tmp_db):
        sub = UserSubscription(user_id="u1", station_id="s1", rrule="FREQ=DAILY")
        tmp_db.add_or_update_subscription(sub)
        tmp_db.delete_subscription("u1", "s1")
        assert len(tmp_db.get_user_subscriptions("u1")) == 0

    def test_delete_subscription_by_id(self, tmp_db):
        sub1 = UserSubscription(user_id="u1", station_id="s1", rrule="FREQ=DAILY")
        sub2 = UserSubscription(user_id="u1", station_id="s1", rrule="FREQ=WEEKLY")
        id1 = tmp_db.add_or_update_subscription(sub1)
        id2 = tmp_db.add_or_update_subscription(sub2)
        tmp_db.delete_subscription_by_id(id1)
        subs = tmp_db.get_user_subscriptions("u1")
        assert len(subs) == 1
        assert subs[0]['rrule'] == "FREQ=WEEKLY"

    def test_delete_all_user_subscriptions(self, tmp_db):
        sub1 = UserSubscription(user_id="u1", station_id="s1", rrule="FREQ=DAILY")
        sub2 = UserSubscription(user_id="u1", station_id="s2", rrule="FREQ=DAILY")
        tmp_db.add_or_update_subscription(sub1)
        tmp_db.add_or_update_subscription(sub2)
        tmp_db.delete_all_user_subscriptions("u1")
        assert len(tmp_db.get_user_subscriptions("u1")) == 0


class TestTaskCRUD:
    def test_add_and_get_pending_tasks(self, tmp_db):
        sub = UserSubscription(user_id="u1", station_id="s1", rrule="FREQ=DAILY")
        sub_id = tmp_db.add_or_update_subscription(sub)
        task = ActiveTask(sub_id=sub_id, next_run="2020-01-01T00:00:00")
        tmp_db.add_task(task)
        # Any time in the future relative to the task's next_run
        tasks = tmp_db.get_pending_tasks("2099-01-01T00:00:00")
        assert len(tasks) == 1
        assert tasks[0]['station_id'] == "s1"
        assert tasks[0]['rrule'] == "FREQ=DAILY"

    def test_update_task_status(self, tmp_db):
        sub = UserSubscription(user_id="u1", station_id="s1", rrule="R")
        sub_id = tmp_db.add_or_update_subscription(sub)
        task = ActiveTask(sub_id=sub_id, next_run="2020-01-01T00:00:00")
        tmp_db.add_task(task)
        tasks = tmp_db.get_pending_tasks("2099-01-01T00:00:00")
        task_id = tasks[0]['id']
        tmp_db.update_task_status(task_id, 'completed')
        # Should no longer be pending
        assert len(tmp_db.get_pending_tasks("2099-01-01T00:00:00")) == 0

    def test_update_task_status_with_next_run(self, tmp_db):
        sub = UserSubscription(user_id="u1", station_id="s1", rrule="R")
        sub_id = tmp_db.add_or_update_subscription(sub)
        task = ActiveTask(sub_id=sub_id, next_run="2020-01-01T00:00:00")
        tmp_db.add_task(task)
        tasks = tmp_db.get_pending_tasks("2099-01-01T00:00:00")
        task_id = tasks[0]['id']
        tmp_db.update_task_status(task_id, 'pending', next_run="2099-06-01T00:00:00", interval=30)
        tasks = tmp_db.get_pending_tasks("2099-06-01T00:00:00")
        assert len(tasks) == 1
        assert tasks[0]['current_interval'] == 30

    def test_delete_completed_tasks(self, tmp_db):
        sub = UserSubscription(user_id="u1", station_id="s1", rrule="R")
        sub_id = tmp_db.add_or_update_subscription(sub)
        task = ActiveTask(sub_id=sub_id, next_run="2020-01-01T00:00:00")
        tmp_db.add_task(task)
        tasks = tmp_db.get_pending_tasks("2099-01-01T00:00:00")
        tmp_db.update_task_status(tasks[0]['id'], 'completed')
        tmp_db.delete_completed_tasks()
        assert len(tmp_db.get_tasks_for_subscription(sub_id)) == 0

    def test_get_tasks_for_subscription(self, tmp_db):
        sub = UserSubscription(user_id="u1", station_id="s1", rrule="R")
        sub_id = tmp_db.add_or_update_subscription(sub)
        t1 = ActiveTask(sub_id=sub_id, next_run="2020-01-01T00:00:00")
        t2 = ActiveTask(sub_id=sub_id, next_run="2020-02-01T00:00:00", status="completed")
        tmp_db.add_task(t1)
        tmp_db.add_task(t2)
        assert len(tmp_db.get_tasks_for_subscription(sub_id)) == 2
        assert len(tmp_db.get_tasks_for_subscription(sub_id, status='pending')) == 1

    def test_delete_subscription_cascades_tasks(self, tmp_db):
        sub = UserSubscription(user_id="u1", station_id="s1", rrule="R")
        sub_id = tmp_db.add_or_update_subscription(sub)
        t = ActiveTask(sub_id=sub_id, next_run="2020-01-01T00:00:00")
        tmp_db.add_task(t)
        tmp_db.delete_subscription("u1", "s1")
        assert len(tmp_db.get_tasks_for_subscription(sub_id)) == 0


class TestStationMetadata:
    def test_save_and_get_stations(self, tmp_db):
        s = StationInfo(sno="001", sna="A站")
        tmp_db.save_stations([s])
        result = tmp_db.get_stations()
        assert len(result) == 1
        assert result[0].sno == "001"

    def test_upsert_stations(self, tmp_db):
        s1 = StationInfo(sno="001", sna="A站")
        s2 = StationInfo(sno="001", sna="A站更新版")
        tmp_db.save_stations([s1])
        tmp_db.save_stations([s2])
        result = tmp_db.get_stations()
        assert len(result) == 1
        assert result[0].sna == "A站更新版"

    def test_get_stations_empty(self, tmp_db):
        assert tmp_db.get_stations() == []


class TestSystemMeta:
    def test_set_and_get_meta(self, tmp_db):
        tmp_db.set_meta("key1", "val1")
        assert tmp_db.get_meta("key1") == "val1"

    def test_get_meta_missing_returns_none(self, tmp_db):
        assert tmp_db.get_meta("nonexistent") is None

    def test_upsert_meta(self, tmp_db):
        tmp_db.set_meta("k", "v1")
        tmp_db.set_meta("k", "v2")
        assert tmp_db.get_meta("k") == "v2"
