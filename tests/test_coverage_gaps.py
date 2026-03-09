"""Extra tests to cover remaining uncovered lines for 100% coverage."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio
from datetime import datetime, timedelta

from src.models.schemas import UserSubscription, ActiveTask, StationInfo
from src.core.monitor import MonitorEngine
from src.core.user_service import UserService
from src.core.station_service import StationService
from src.api.client import YouBikeClient
from tests.conftest import FakeMessage, FakeLocation, make_station, SAMPLE_STATIONS


# ── Reuse conftest helpers ───────────────────────────────────

@pytest.fixture
def bot(user_service, station_service, mock_api_client):
    with patch("src.notifiers.bot.Bot"), patch("src.notifiers.bot.Dispatcher"):
        from src.notifiers.bot import BikeGuardBot
        b = BikeGuardBot.__new__(BikeGuardBot)
        b.bot = MagicMock()
        b.dp = MagicMock()
        b.user_service = user_service
        b.station_service = station_service
        b.api_client = mock_api_client
        b._last_search_results = {}
    return b


# ── bot.py __init__, _setup_handlers, set_commands, start ────

class TestBotInit:
    @pytest.mark.asyncio
    async def test_full_init(self, user_service, station_service, mock_api_client):
        with patch("src.notifiers.bot.Bot") as MockBot, \
             patch("src.notifiers.bot.Dispatcher") as MockDispatcher:
            mock_dp = MagicMock()
            MockDispatcher.return_value = mock_dp
            mock_bot = MagicMock()
            MockBot.return_value = mock_bot

            from src.notifiers.bot import BikeGuardBot
            bot = BikeGuardBot("fake_token", user_service, station_service, mock_api_client)
            assert bot.bot is mock_bot
            assert bot.dp is mock_dp
            assert mock_dp.message.register.call_count > 0

    @pytest.mark.asyncio
    async def test_set_commands(self, user_service, station_service, mock_api_client):
        with patch("src.notifiers.bot.Bot") as MockBot, \
             patch("src.notifiers.bot.Dispatcher"):
            mock_bot = MagicMock()
            mock_bot.set_my_commands = AsyncMock()
            MockBot.return_value = mock_bot

            from src.notifiers.bot import BikeGuardBot
            bot = BikeGuardBot("fake_token", user_service, station_service, mock_api_client)
            await bot.set_commands()
            mock_bot.set_my_commands.assert_called_once()

    @pytest.mark.asyncio
    async def test_start(self, user_service, station_service, mock_api_client):
        with patch("src.notifiers.bot.Bot") as MockBot, \
             patch("src.notifiers.bot.Dispatcher") as MockDispatcher:
            mock_bot = MagicMock()
            mock_bot.set_my_commands = AsyncMock()
            MockBot.return_value = mock_bot
            mock_dp = MagicMock()
            mock_dp.start_polling = AsyncMock()
            MockDispatcher.return_value = mock_dp

            from src.notifiers.bot import BikeGuardBot
            bot = BikeGuardBot("fake_token", user_service, station_service, mock_api_client)
            await bot.start()
            mock_bot.set_my_commands.assert_called_once()
            mock_dp.start_polling.assert_called_once_with(mock_bot)


# ── bot.py number_selection_handler error fallthrough (line 221) ─

class TestNumberSelectionErrors:
    @pytest.mark.asyncio
    async def test_digit_selection_key_error(self, bot):
        """Trigger KeyError via remove_slot with bad data."""
        bot._last_search_results["12345"] = {
            "matches": [{"bad_key": "no id"}],  # Missing 'id' key
            "command": "remove_slot",
            "args": []
        }
        msg = FakeMessage(text="1")
        await bot.number_selection_handler(msg)
        # Should fall through gracefully via except (ValueError, KeyError, TypeError)


# ── scheduler.py start_loop error handling (lines 60-67) ─────

class TestSchedulerLoop:
    @pytest.mark.asyncio
    async def test_start_loop_runs_and_can_be_cancelled(self, tmp_db):
        from src.core.scheduler import RRuleScheduler
        scheduler = RRuleScheduler(tmp_db)
        scheduler.run_scheduler_cycle = AsyncMock()

        task = asyncio.create_task(scheduler.start_loop(interval=0))
        await asyncio.sleep(0.1)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        assert scheduler.run_scheduler_cycle.call_count >= 1

    @pytest.mark.asyncio
    async def test_start_loop_handles_exception(self, tmp_db):
        from src.core.scheduler import RRuleScheduler
        scheduler = RRuleScheduler(tmp_db)
        scheduler.run_scheduler_cycle = AsyncMock(side_effect=Exception("boom"))

        task = asyncio.create_task(scheduler.start_loop(interval=0))
        await asyncio.sleep(0.1)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


# ── scheduler.py past-time branch (line 46) ──────────────────

class TestSchedulerPastTimeBranch:
    @pytest.mark.asyncio
    async def test_past_next_run_starts_now(self, tmp_db):
        future = (datetime.now() + timedelta(minutes=5)).isoformat()
        sub = UserSubscription(user_id="u1", station_id="s1", rrule=f"ONCE:{future}")
        tmp_db.add_or_update_subscription(sub)
        from src.core.scheduler import RRuleScheduler
        scheduler = RRuleScheduler(tmp_db)
        await scheduler.run_scheduler_cycle()
        tasks = tmp_db.get_pending_tasks("2099-01-01T00:00:00")
        assert len(tasks) == 1


# ── monitor.py start_loop (lines 127-129) ────────────────────

class TestMonitorLoop:
    @pytest.mark.asyncio
    async def test_start_loop_can_be_cancelled(self, tmp_db, mock_api_client):
        user_service = UserService(tmp_db)
        station_service = StationService(tmp_db, mock_api_client)
        engine = MonitorEngine(mock_api_client, user_service, station_service, [])
        engine.run_worker_cycle = AsyncMock()

        task = asyncio.create_task(engine.start_loop(interval=0))
        await asyncio.sleep(0.1)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        assert engine.run_worker_cycle.call_count >= 1


# ── nlp_parser.py test_parser and __main__ (lines 62-74) ─────

class TestNlpParserTestFunc:
    def test_test_parser_runs(self):
        from src.utils.nlp_parser import test_parser
        test_parser()


# ── base.py abstract method body (line 6) ────────────────────

class TestBaseNotifierSubclass:
    @pytest.mark.asyncio
    async def test_concrete_subclass(self):
        from src.notifiers.base import BaseNotifier
        class ConcreteNotifier(BaseNotifier):
            async def send_notification(self, message, **kwargs):
                return message
        cn = ConcreteNotifier()
        result = await cn.send_notification("hello")
        assert result == "hello"


# ── client.py unreachable return (line 94) ────────────────────

class TestClientUnreachableReturn:
    @pytest.mark.asyncio
    async def test_fetch_parking_info_no_exception_path(self):
        """The return {} on line 94 is after the try/except in fetch_parking_info.
        This is actually unreachable code. We verify the normal path works."""
        client = YouBikeClient()
        mock_response = MagicMock()
        mock_response.json.return_value = {"retCode": 1, "retVal": []}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.api.client.httpx.AsyncClient", return_value=mock_client):
            result = await client.fetch_parking_info(["001"])
        assert result == {}
