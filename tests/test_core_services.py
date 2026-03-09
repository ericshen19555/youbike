"""Tests for src/core/user_service.py, src/core/station_service.py, src/core/scheduler.py."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from src.core.user_service import UserService
from src.core.station_service import StationService
from src.core.scheduler import RRuleScheduler
from src.models.schemas import UserSubscription, StationInfo


# ── UserService ──────────────────────────────────────────────

class TestUserService:
    @pytest.mark.asyncio
    async def test_register_subscription(self, user_service):
        sub_id = await user_service.register_subscription("u1", "s1", 5, "FREQ=DAILY")
        assert sub_id is not None

    def test_get_subscriptions(self, user_service, tmp_db):
        sub = UserSubscription(user_id="u1", station_id="s1", rrule="R")
        tmp_db.add_or_update_subscription(sub)
        subs = user_service.get_subscriptions("u1")
        assert len(subs) == 1

    def test_get_user_station_subscriptions(self, user_service, tmp_db):
        sub1 = UserSubscription(user_id="u1", station_id="s1", rrule="R1")
        sub2 = UserSubscription(user_id="u1", station_id="s1", rrule="R2")
        tmp_db.add_or_update_subscription(sub1)
        tmp_db.add_or_update_subscription(sub2)
        result = user_service.get_user_station_subscriptions("u1", "s1")
        assert len(result) == 2

    def test_remove_subscription(self, user_service, tmp_db):
        sub = UserSubscription(user_id="u1", station_id="s1", rrule="R")
        tmp_db.add_or_update_subscription(sub)
        assert user_service.remove_subscription("u1", "s1") is True
        assert len(user_service.get_subscriptions("u1")) == 0

    def test_remove_subscription_by_id(self, user_service, tmp_db):
        sub = UserSubscription(user_id="u1", station_id="s1", rrule="R")
        sid = tmp_db.add_or_update_subscription(sub)
        assert user_service.remove_subscription_by_id(sid) is True

    def test_clear_all_subscriptions(self, user_service, tmp_db):
        sub1 = UserSubscription(user_id="u1", station_id="s1", rrule="R")
        sub2 = UserSubscription(user_id="u1", station_id="s2", rrule="R")
        tmp_db.add_or_update_subscription(sub1)
        tmp_db.add_or_update_subscription(sub2)
        assert user_service.clear_all_subscriptions("u1") is True
        assert len(user_service.get_subscriptions("u1")) == 0


# ── StationService ───────────────────────────────────────────

class TestStationService:
    @pytest.mark.asyncio
    async def test_get_stations_fetches_from_api_when_empty(self, station_service, mock_api_client):
        stations = await station_service.get_stations()
        assert len(stations) > 0
        mock_api_client.fetch_station_list.assert_called_once()

    @pytest.mark.asyncio
    async def test_memory_cache_hit(self, station_service, mock_api_client):
        await station_service.get_stations()
        await station_service.get_stations()
        # Only 1 API call (memory cache serves second)
        assert mock_api_client.fetch_station_list.call_count == 1

    @pytest.mark.asyncio
    async def test_force_refresh(self, station_service, mock_api_client):
        await station_service.get_stations()
        await station_service.get_stations(force_refresh=True)
        assert mock_api_client.fetch_station_list.call_count == 2

    @pytest.mark.asyncio
    async def test_db_cache_hit_within_24h(self, station_service, tmp_db, mock_api_client):
        # Pre-populate DB
        s = StationInfo(sno="001", sna="A")
        tmp_db.save_stations([s])
        tmp_db.set_meta("last_station_sync", datetime.now().isoformat())
        # Reset memory cache
        station_service._memory_cache = []
        station_service._last_refresh = None
        stations = await station_service.get_stations()
        assert len(stations) == 1
        mock_api_client.fetch_station_list.assert_not_called()

    @pytest.mark.asyncio
    async def test_db_stale_triggers_api(self, station_service, tmp_db, mock_api_client):
        s = StationInfo(sno="001", sna="A")
        tmp_db.save_stations([s])
        old_time = (datetime.now() - timedelta(hours=25)).isoformat()
        tmp_db.set_meta("last_station_sync", old_time)
        station_service._memory_cache = []
        station_service._last_refresh = None
        await station_service.get_stations()
        mock_api_client.fetch_station_list.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalid_sync_time_triggers_api(self, station_service, tmp_db, mock_api_client):
        s = StationInfo(sno="001", sna="A")
        tmp_db.save_stations([s])
        tmp_db.set_meta("last_station_sync", "not-a-date")
        station_service._memory_cache = []
        station_service._last_refresh = None
        await station_service.get_stations()
        mock_api_client.fetch_station_list.assert_called_once()

    @pytest.mark.asyncio
    async def test_api_fails_returns_db_data(self, station_service, tmp_db, mock_api_client):
        s = StationInfo(sno="001", sna="A")
        tmp_db.save_stations([s])
        mock_api_client.fetch_station_list = AsyncMock(return_value=[])
        station_service._memory_cache = []
        station_service._last_refresh = None
        stations = await station_service.get_stations(force_refresh=True)
        assert len(stations) == 1  # falls back to DB

    @pytest.mark.asyncio
    async def test_api_fails_db_empty_returns_empty(self, tmp_db, mock_api_client):
        mock_api_client.fetch_station_list = AsyncMock(return_value=[])
        ss = StationService(tmp_db, mock_api_client)
        stations = await ss.get_stations()
        assert stations == []

    @pytest.mark.asyncio
    async def test_find_station_by_id(self, station_service):
        await station_service.get_stations()  # populate
        found = await station_service.find_station_by_id("500101001")
        assert found is not None
        assert found.sna == "科技大樓"

    @pytest.mark.asyncio
    async def test_find_station_by_id_not_found(self, station_service):
        await station_service.get_stations()
        assert await station_service.find_station_by_id("999999999") is None


# ── RRuleScheduler ───────────────────────────────────────────

class TestRRuleScheduler:
    @pytest.mark.asyncio
    async def test_schedules_task_for_active_sub(self, tmp_db):
        sub = UserSubscription(user_id="u1", station_id="s1", rrule="FREQ=DAILY;BYHOUR=23;BYMINUTE=59")
        tmp_db.add_or_update_subscription(sub)
        scheduler = RRuleScheduler(tmp_db)
        await scheduler.run_scheduler_cycle()
        tasks = tmp_db.get_pending_tasks("2099-01-01T00:00:00")
        assert len(tasks) >= 1

    @pytest.mark.asyncio
    async def test_no_duplicate_task_if_pending_exists(self, tmp_db):
        sub = UserSubscription(user_id="u1", station_id="s1", rrule="FREQ=DAILY;BYHOUR=23;BYMINUTE=59")
        tmp_db.add_or_update_subscription(sub)
        scheduler = RRuleScheduler(tmp_db)
        await scheduler.run_scheduler_cycle()
        await scheduler.run_scheduler_cycle()
        tasks = tmp_db.get_pending_tasks("2099-01-01T00:00:00")
        assert len(tasks) == 1  # should not duplicate

    @pytest.mark.asyncio
    async def test_no_task_if_rrule_invalid(self, tmp_db):
        sub = UserSubscription(user_id="u1", station_id="s1", rrule="INVALID")
        tmp_db.add_or_update_subscription(sub)
        scheduler = RRuleScheduler(tmp_db)
        await scheduler.run_scheduler_cycle()
        tasks = tmp_db.get_pending_tasks("2099-01-01T00:00:00")
        assert len(tasks) == 0

    @pytest.mark.asyncio
    async def test_once_in_future_schedules(self, tmp_db):
        future = (datetime.now() + timedelta(hours=1)).isoformat()
        sub = UserSubscription(user_id="u1", station_id="s1", rrule=f"ONCE:{future}")
        tmp_db.add_or_update_subscription(sub)
        scheduler = RRuleScheduler(tmp_db)
        await scheduler.run_scheduler_cycle()
        tasks = tmp_db.get_pending_tasks("2099-01-01T00:00:00")
        assert len(tasks) == 1
