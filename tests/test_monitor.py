"""Tests for src/core/monitor.py — MonitorEngine worker cycle."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from src.core.monitor import MonitorEngine
from src.core.user_service import UserService
from src.core.station_service import StationService
from src.api.client import YouBikeClient
from src.models.schemas import UserSubscription, ActiveTask, StationInfo
from tests.conftest import make_station


@pytest.fixture
def monitor_deps(tmp_db):
    """Create all dependencies for MonitorEngine."""
    user_service = UserService(tmp_db)
    api_client = MagicMock(spec=YouBikeClient)
    api_client.fetch_parking_info = AsyncMock(return_value={})
    api_client.fetch_station_list = AsyncMock(return_value=[
        make_station(sno="s1", sna="站A"),
    ])
    station_service = StationService(tmp_db, api_client)
    notifier = MagicMock()
    notifier.send_notification = AsyncMock()
    return tmp_db, user_service, api_client, station_service, notifier


def _make_engine(deps, notifiers=None):
    tmp_db, user_service, api_client, station_service, notifier = deps
    return MonitorEngine(api_client, user_service, station_service, notifiers or [notifier])





class TestRunWorkerCycle:
    @pytest.mark.asyncio
    async def test_no_tasks_returns_early(self, monitor_deps):
        engine = _make_engine(monitor_deps)
        await engine.run_worker_cycle()  # Should not error

    @pytest.mark.asyncio
    async def test_triggered_sends_notification(self, monitor_deps):
        tmp_db, user_service, api_client, station_service, notifier = monitor_deps
        sub = UserSubscription(user_id="u1", station_id="s1", rrule="FREQ=DAILY")
        sub_id = tmp_db.add_or_update_subscription(sub)
        task = ActiveTask(sub_id=sub_id, next_run="2020-01-01T00:00:00")
        tmp_db.add_task(task)

        api_client.fetch_parking_info = AsyncMock(return_value={
            "s1": {"tot": 30, "sbi": 2, "sbi_20": 1, "sbi_20e": 1, "bemp": 28, "updatetime": "now", "isRealtime": True}
        })

        engine = _make_engine(monitor_deps)
        await engine.run_worker_cycle()
        notifier.send_notification.assert_called_once()

    @pytest.mark.asyncio
    async def test_not_triggered_no_notification(self, monitor_deps):
        tmp_db, user_service, api_client, station_service, notifier = monitor_deps
        sub = UserSubscription(user_id="u1", station_id="s1", rrule="FREQ=DAILY")
        sub_id = tmp_db.add_or_update_subscription(sub)
        task = ActiveTask(sub_id=sub_id, next_run="2020-01-01T00:00:00")
        tmp_db.add_task(task)

        api_client.fetch_parking_info = AsyncMock(return_value={
            "s1": {"tot": 30, "sbi": 20, "sbi_20": 12, "sbi_20e": 8, "bemp": 10, "updatetime": "now", "isRealtime": True}
        })

        engine = _make_engine(monitor_deps)
        await engine.run_worker_cycle()
        notifier.send_notification.assert_not_called()

    @pytest.mark.asyncio
    async def test_medium_interval(self, monitor_deps):
        """Count between threshold and threshold*2 → medium interval."""
        tmp_db, user_service, api_client, station_service, notifier = monitor_deps
        sub = UserSubscription(user_id="u1", station_id="s1", rrule="FREQ=DAILY", threshold=3)
        sub_id = tmp_db.add_or_update_subscription(sub)
        task = ActiveTask(sub_id=sub_id, next_run="2020-01-01T00:00:00")
        tmp_db.add_task(task)

        # sbi=5 > threshold(3) but <= threshold*2(6)
        api_client.fetch_parking_info = AsyncMock(return_value={
            "s1": {"tot": 30, "sbi": 5, "sbi_20": 3, "sbi_20e": 2, "bemp": 25, "updatetime": "now", "isRealtime": True}
        })

        engine = _make_engine(monitor_deps)
        await engine.run_worker_cycle()
        notifier.send_notification.assert_not_called()

    @pytest.mark.asyncio
    async def test_bike_type_normal(self, monitor_deps):
        tmp_db, user_service, api_client, station_service, notifier = monitor_deps
        sub = UserSubscription(user_id="u1", station_id="s1", rrule="FREQ=DAILY", bike_type="normal", threshold=5)
        sub_id = tmp_db.add_or_update_subscription(sub)
        task = ActiveTask(sub_id=sub_id, next_run="2020-01-01T00:00:00")
        tmp_db.add_task(task)

        api_client.fetch_parking_info = AsyncMock(return_value={
            "s1": {"tot": 30, "sbi": 20, "sbi_20": 2, "sbi_20e": 18, "bemp": 10, "updatetime": "now", "isRealtime": True}
        })

        engine = _make_engine(monitor_deps)
        await engine.run_worker_cycle()
        notifier.send_notification.assert_called_once()  # sbi_20=2 < threshold=5

    @pytest.mark.asyncio
    async def test_bike_type_electric(self, monitor_deps):
        tmp_db, user_service, api_client, station_service, notifier = monitor_deps
        sub = UserSubscription(user_id="u1", station_id="s1", rrule="FREQ=DAILY", bike_type="electric", threshold=3)
        sub_id = tmp_db.add_or_update_subscription(sub)
        task = ActiveTask(sub_id=sub_id, next_run="2020-01-01T00:00:00")
        tmp_db.add_task(task)

        api_client.fetch_parking_info = AsyncMock(return_value={
            "s1": {"tot": 30, "sbi": 20, "sbi_20": 18, "sbi_20e": 2, "bemp": 10, "updatetime": "now", "isRealtime": True}
        })

        engine = _make_engine(monitor_deps)
        await engine.run_worker_cycle()
        notifier.send_notification.assert_called_once()  # sbi_20e=2 < threshold=3

    @pytest.mark.asyncio
    async def test_once_task_deleted_after_trigger(self, monitor_deps):
        tmp_db, user_service, api_client, station_service, notifier = monitor_deps
        future = (datetime.now() + timedelta(hours=1)).isoformat()
        sub = UserSubscription(user_id="u1", station_id="s1", rrule=f"ONCE:{future}")
        sub_id = tmp_db.add_or_update_subscription(sub)
        task = ActiveTask(sub_id=sub_id, next_run="2020-01-01T00:00:00")
        tmp_db.add_task(task)

        api_client.fetch_parking_info = AsyncMock(return_value={
            "s1": {"tot": 30, "sbi": 1, "sbi_20": 1, "sbi_20e": 0, "bemp": 29, "updatetime": "now", "isRealtime": True}
        })

        engine = _make_engine(monitor_deps)
        await engine.run_worker_cycle()
        # Subscription should be deleted
        assert len(tmp_db.get_user_subscriptions("u1")) == 0

    @pytest.mark.asyncio
    async def test_station_not_in_realtime_skipped(self, monitor_deps):
        tmp_db, user_service, api_client, station_service, notifier = monitor_deps
        sub = UserSubscription(user_id="u1", station_id="s1", rrule="FREQ=DAILY")
        sub_id = tmp_db.add_or_update_subscription(sub)
        task = ActiveTask(sub_id=sub_id, next_run="2020-01-01T00:00:00")
        tmp_db.add_task(task)

        api_client.fetch_parking_info = AsyncMock(return_value={})  # No data for s1
        engine = _make_engine(monitor_deps)
        await engine.run_worker_cycle()
        notifier.send_notification.assert_not_called()


class TestRunOnceAndLoop:
    @pytest.mark.asyncio
    async def test_run_once_delegates_to_worker_cycle(self, monitor_deps):
        engine = _make_engine(monitor_deps)
        engine.run_worker_cycle = AsyncMock()
        await engine.run_once()
        engine.run_worker_cycle.assert_called_once()
