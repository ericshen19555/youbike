"""Tests for src/notifiers/bot.py — BikeGuardBot with simulated Telegram messages.

Uses FakeMessage from conftest to simulate Telegram interactions without
any real network calls; all dependencies are mocked or use temp-DB fixtures.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from src.models.schemas import StationInfo, UserSubscription
from tests.conftest import FakeMessage, FakeLocation, make_station, SAMPLE_STATIONS


# ── Helpers ──────────────────────────────────────────────────

def _create_bot(user_service, station_service, mock_api_client):
    """Build a BikeGuardBot without actually starting aiogram Dispatcher."""
    with patch("src.notifiers.bot.Bot"), patch("src.notifiers.bot.Dispatcher"):
        from src.notifiers.bot import BikeGuardBot
        bot = BikeGuardBot.__new__(BikeGuardBot)
        bot.bot = MagicMock()
        bot.dp = MagicMock()
        bot.user_service = user_service
        bot.station_service = station_service
        bot.api_client = mock_api_client
        bot._last_search_results = {}
    return bot


@pytest.fixture
def bot(user_service, station_service, mock_api_client):
    return _create_bot(user_service, station_service, mock_api_client)


# ── /start & /help ───────────────────────────────────────────

class TestStartHandler:
    @pytest.mark.asyncio
    async def test_start(self, bot):
        msg = FakeMessage(text="/start")
        await bot.start_handler(msg)
        msg.answer.assert_called_once()
        text = msg.answer.call_args[0][0]
        assert "BikeGuard" in text

    @pytest.mark.asyncio
    async def test_start_cancels_pending(self, bot):
        bot._last_search_results["12345"] = {"command": "add", "matches": [], "args": []}
        msg = FakeMessage(text="/start")
        await bot.start_handler(msg)
        assert "12345" not in bot._last_search_results


# ── /add ─────────────────────────────────────────────────────

class TestAddHandler:
    @pytest.mark.asyncio
    async def test_no_args_shows_help(self, bot):
        msg = FakeMessage(text="/add")
        await bot.add_handler(msg)
        text = msg.answer.call_args[0][0]
        assert "格式" in text

    @pytest.mark.asyncio
    async def test_single_match_registers(self, bot):
        msg = FakeMessage(text="/add 中山國小 5 每天 08:30")
        await bot.add_handler(msg)
        text = msg.answer.call_args[0][0]
        assert "監控已開啟" in text

    @pytest.mark.asyncio
    async def test_no_match(self, bot):
        msg = FakeMessage(text="/add 不存在的站")
        await bot.add_handler(msg)
        text = msg.answer.call_args[0][0]
        assert "找不到" in text

    @pytest.mark.asyncio
    async def test_multiple_matches(self, bot):
        msg = FakeMessage(text="/add 科技")
        await bot.add_handler(msg)
        text = msg.answer.call_args[0][0]
        assert "編號" in text
        assert "12345" in bot._last_search_results


# ── _register_sub_with_station ───────────────────────────────

class TestRegisterSub:
    @pytest.mark.asyncio
    async def test_default_once_reminder(self, bot):
        """No time args → defaults to 30min once."""
        msg = FakeMessage(text="/add 中山國小")
        station = SAMPLE_STATIONS[2]
        await bot._register_sub_with_station(msg, station, [])
        text = msg.answer.call_args[0][0]
        assert "單次提醒" in text

    @pytest.mark.asyncio
    async def test_with_threshold_only(self, bot):
        msg = FakeMessage()
        station = SAMPLE_STATIONS[2]
        await bot._register_sub_with_station(msg, station, ["5"])
        text = msg.answer.call_args[0][0]
        assert "5" in text

    @pytest.mark.asyncio
    async def test_with_electric_type(self, bot):
        msg = FakeMessage()
        station = SAMPLE_STATIONS[2]
        await bot._register_sub_with_station(msg, station, ["3", "每天", "08:30", "電輔"])
        text = msg.answer.call_args[0][0]
        assert "電輔" in text

    @pytest.mark.asyncio
    async def test_with_normal_type(self, bot):
        msg = FakeMessage()
        station = SAMPLE_STATIONS[2]
        await bot._register_sub_with_station(msg, station, ["3", "每天", "08:30", "普通"])
        text = msg.answer.call_args[0][0]
        assert "一般" in text

    @pytest.mark.asyncio
    async def test_with_一般_type(self, bot):
        msg = FakeMessage()
        station = SAMPLE_STATIONS[2]
        await bot._register_sub_with_station(msg, station, ["3", "每天", "08:30", "一般"])
        text = msg.answer.call_args[0][0]
        assert "一般" in text

    @pytest.mark.asyncio
    async def test_invalid_threshold_defaults(self, bot):
        msg = FakeMessage()
        station = SAMPLE_STATIONS[2]
        await bot._register_sub_with_station(msg, station, ["abc", "每天", "08:30"])
        text = msg.answer.call_args[0][0]
        assert "3" in text  # DEFAULT_THRESHOLD


# ── /query ───────────────────────────────────────────────────

class TestQueryHandler:
    @pytest.mark.asyncio
    async def test_no_args_shows_help(self, bot):
        msg = FakeMessage(text="/query")
        await bot.query_handler(msg)
        text = msg.answer.call_args[0][0]
        assert "query" in text

    @pytest.mark.asyncio
    async def test_single_match(self, bot):
        bot.api_client.fetch_parking_info = AsyncMock(return_value={
            "500102003": {"sbi_20": 5, "sbi_20e": 3, "bemp": 22, "updatetime": "now"}
        })
        msg = FakeMessage(text="/query 中山國小")
        await bot.query_handler(msg)
        text = msg.answer.call_args[0][0]
        assert "中山國小" in text

    @pytest.mark.asyncio
    async def test_multiple_matches(self, bot):
        msg = FakeMessage(text="/query 科技")
        await bot.query_handler(msg)
        text = msg.answer.call_args[0][0]
        assert "編號" in text

    @pytest.mark.asyncio
    async def test_no_match(self, bot):
        msg = FakeMessage(text="/query 不存在")
        await bot.query_handler(msg)
        text = msg.answer.call_args[0][0]
        assert "找不到" in text


# ── /list ────────────────────────────────────────────────────

class TestListHandler:
    @pytest.mark.asyncio
    async def test_empty_list(self, bot):
        msg = FakeMessage()
        await bot.list_handler(msg)
        text = msg.answer.call_args[0][0]
        assert "沒有" in text

    @pytest.mark.asyncio
    async def test_with_subscriptions(self, bot, tmp_db):
        sub = UserSubscription(user_id="12345", station_id="500101001", rrule="FREQ=DAILY",
                               bike_type="electric", threshold=5)
        tmp_db.add_or_update_subscription(sub)
        msg = FakeMessage()
        await bot.list_handler(msg)
        text = msg.answer.call_args[0][0]
        assert "科技大樓" in text
        assert "電輔" in text


# ── /remove ──────────────────────────────────────────────────

class TestRemoveHandler:
    @pytest.mark.asyncio
    async def test_no_args_shows_help(self, bot):
        msg = FakeMessage(text="/remove")
        await bot.remove_handler(msg)
        text = msg.answer.call_args[0][0]
        assert "格式" in text or "remove" in text

    @pytest.mark.asyncio
    async def test_remove_all(self, bot, tmp_db):
        sub = UserSubscription(user_id="12345", station_id="s1", rrule="R")
        tmp_db.add_or_update_subscription(sub)
        msg = FakeMessage(text="/remove all")
        await bot.remove_handler(msg)
        text = msg.answer.call_args[0][0]
        assert "清空" in text

    @pytest.mark.asyncio
    async def test_remove_no_subscriptions(self, bot):
        msg = FakeMessage(text="/remove 科技大樓")
        await bot.remove_handler(msg)
        text = msg.answer.call_args[0][0]
        assert "沒有" in text

    @pytest.mark.asyncio
    async def test_remove_single_match_single_sub(self, bot, tmp_db):
        sub = UserSubscription(user_id="12345", station_id="500102003", rrule="FREQ=DAILY")
        tmp_db.add_or_update_subscription(sub)
        msg = FakeMessage(text="/remove 中山國小")
        await bot.remove_handler(msg)
        text = msg.answer.call_args[0][0]
        assert "移除" in text

    @pytest.mark.asyncio
    async def test_remove_single_match_multiple_subs_shows_slots(self, bot, tmp_db):
        sub1 = UserSubscription(user_id="12345", station_id="500102003", rrule="FREQ=DAILY")
        sub2 = UserSubscription(user_id="12345", station_id="500102003", rrule="FREQ=WEEKLY")
        tmp_db.add_or_update_subscription(sub1)
        tmp_db.add_or_update_subscription(sub2)
        msg = FakeMessage(text="/remove 中山國小")
        await bot.remove_handler(msg)
        text = msg.answer.call_args[0][0]
        assert "編號" in text
        assert "12345" in bot._last_search_results

    @pytest.mark.asyncio
    async def test_remove_station_not_in_subscriptions(self, bot, tmp_db):
        sub = UserSubscription(user_id="12345", station_id="500102003", rrule="R")
        tmp_db.add_or_update_subscription(sub)
        msg = FakeMessage(text="/remove 不存在")
        await bot.remove_handler(msg)
        text = msg.answer.call_args[0][0]
        assert "找不到" in text

    @pytest.mark.asyncio
    async def test_remove_multiple_station_matches(self, bot, tmp_db):
        sub1 = UserSubscription(user_id="12345", station_id="500101001", rrule="R")
        sub2 = UserSubscription(user_id="12345", station_id="500101002", rrule="R")
        tmp_db.add_or_update_subscription(sub1)
        tmp_db.add_or_update_subscription(sub2)
        msg = FakeMessage(text="/remove 科技")
        await bot.remove_handler(msg)
        text = msg.answer.call_args[0][0]
        assert "編號" in text

    @pytest.mark.asyncio
    async def test_check_and_process_no_subs(self, bot):
        station = SAMPLE_STATIONS[0]
        msg = FakeMessage()
        await bot._check_and_process_remove_selection(msg, station)
        text = msg.answer.call_args[0][0]
        assert "沒有訂閱" in text


# ── number_selection_handler ─────────────────────────────────

class TestNumberSelectionHandler:
    @pytest.mark.asyncio
    async def test_digit_selection_add(self, bot):
        bot._last_search_results["12345"] = {
            "matches": SAMPLE_STATIONS,
            "command": "add",
            "args": ["5", "每天", "08:30"]
        }
        msg = FakeMessage(text="3")  # Select index 3 → 中山國小
        await bot.number_selection_handler(msg)
        text = msg.answer.call_args[0][0]
        assert "監控已開啟" in text

    @pytest.mark.asyncio
    async def test_digit_selection_query(self, bot):
        bot.api_client.fetch_parking_info = AsyncMock(return_value={
            "500102003": {"sbi_20": 5, "sbi_20e": 3, "bemp": 22, "updatetime": "now"}
        })
        bot._last_search_results["12345"] = {
            "matches": SAMPLE_STATIONS,
            "command": "query",
            "args": []
        }
        msg = FakeMessage(text="3")
        await bot.number_selection_handler(msg)
        text = msg.answer.call_args[0][0]
        assert "中山國小" in text

    @pytest.mark.asyncio
    async def test_digit_selection_remove(self, bot, tmp_db):
        sub = UserSubscription(user_id="12345", station_id="500102003", rrule="R")
        tmp_db.add_or_update_subscription(sub)
        bot._last_search_results["12345"] = {
            "matches": SAMPLE_STATIONS,
            "command": "remove",
            "args": []
        }
        msg = FakeMessage(text="3")
        await bot.number_selection_handler(msg)
        text = msg.answer.call_args[0][0]
        assert "移除" in text

    @pytest.mark.asyncio
    async def test_digit_selection_remove_slot(self, bot, tmp_db):
        sub = UserSubscription(user_id="12345", station_id="500102003", rrule="R")
        sub_id = tmp_db.add_or_update_subscription(sub)
        subs = tmp_db.get_user_station_subscriptions("12345", "500102003")
        bot._last_search_results["12345"] = {
            "matches": subs,
            "command": "remove_slot",
            "args": []
        }
        msg = FakeMessage(text="1")
        await bot.number_selection_handler(msg)
        text = msg.answer.call_args[0][0]
        assert "移除" in text

    @pytest.mark.asyncio
    async def test_digit_out_of_range_falls_through(self, bot):
        bot._last_search_results["12345"] = {
            "matches": SAMPLE_STATIONS,
            "command": "add",
            "args": []
        }
        msg = FakeMessage(text="99")
        await bot.number_selection_handler(msg)
        # Falls through to re-search path; state is cleared

    @pytest.mark.asyncio
    async def test_text_re_search_add(self, bot):
        bot._last_search_results["12345"] = {
            "matches": SAMPLE_STATIONS,
            "command": "add",
            "args": ["5"]
        }
        msg = FakeMessage(text="中山國小")
        await bot.number_selection_handler(msg)
        text = msg.answer.call_args[0][0]
        assert "監控已開啟" in text

    @pytest.mark.asyncio
    async def test_text_re_search_query(self, bot):
        bot.api_client.fetch_parking_info = AsyncMock(return_value={
            "500102003": {"sbi_20": 5, "sbi_20e": 3, "bemp": 22, "updatetime": "now"}
        })
        bot._last_search_results["12345"] = {
            "matches": SAMPLE_STATIONS,
            "command": "query",
            "args": []
        }
        msg = FakeMessage(text="中山國小")
        await bot.number_selection_handler(msg)

    @pytest.mark.asyncio
    async def test_text_re_search_remove(self, bot, tmp_db):
        sub = UserSubscription(user_id="12345", station_id="500102003", rrule="R")
        tmp_db.add_or_update_subscription(sub)
        bot._last_search_results["12345"] = {
            "matches": SAMPLE_STATIONS,
            "command": "remove",
            "args": []
        }
        msg = FakeMessage(text="中山國小")
        await bot.number_selection_handler(msg)

    @pytest.mark.asyncio
    async def test_unknown_command_falls_to_text_handler(self, bot):
        bot._last_search_results["12345"] = {
            "matches": SAMPLE_STATIONS,
            "command": "unknown_cmd",
            "args": []
        }
        msg = FakeMessage(text="anything")
        await bot.number_selection_handler(msg)
        # Should call text_handler as fallback

    @pytest.mark.asyncio
    async def test_no_pending_state_returns(self, bot):
        msg = FakeMessage(text="1")
        # No state in _last_search_results
        await bot.number_selection_handler(msg)
        msg.answer.assert_not_called()


# ── /cancel ──────────────────────────────────────────────────

class TestCancelHandler:
    @pytest.mark.asyncio
    async def test_cancel_clears_state(self, bot):
        bot._last_search_results["12345"] = {"command": "add"}
        msg = FakeMessage(text="/cancel")
        await bot.cancel_handler(msg)
        assert "12345" not in bot._last_search_results

    @pytest.mark.asyncio
    async def test_cancel_no_state(self, bot):
        msg = FakeMessage(text="/cancel")
        await bot.cancel_handler(msg)
        text = msg.answer.call_args[0][0]
        assert "取消" in text


# ── location_handler ─────────────────────────────────────────

class TestLocationHandler:
    @pytest.mark.asyncio
    async def test_location_returns_nearest(self, bot):
        msg = FakeMessage(location=FakeLocation(25.033, 121.565))
        await bot.location_handler(msg)
        text = msg.answer.call_args[0][0]
        assert "最近" in text


# ── text_handler (catch-all) ─────────────────────────────────

class TestTextHandler:
    @pytest.mark.asyncio
    async def test_station_search(self, bot):
        msg = FakeMessage(text="科技大樓")
        await bot.text_handler(msg)
        text = msg.answer.call_args[0][0]
        assert "找到" in text

    @pytest.mark.asyncio
    async def test_too_short_text(self, bot):
        msg = FakeMessage(text="a")
        await bot.text_handler(msg)
        text = msg.answer.call_args[0][0]
        assert "抱歉" in text or "help" in text.lower() or "指令" in text

    @pytest.mark.asyncio
    async def test_nlp_with_station_id(self, bot):
        msg = FakeMessage(text="每天 08:30 500101001")
        await bot.text_handler(msg)
        text = msg.answer.call_args[0][0]
        assert "聽懂" in text

    @pytest.mark.asyncio
    async def test_nlp_with_electric(self, bot):
        msg = FakeMessage(text="每天 08:30 500101001 電輔")
        await bot.text_handler(msg)
        text = msg.answer.call_args[0][0]
        assert "電輔" in text

    @pytest.mark.asyncio
    async def test_nlp_with_normal(self, bot):
        msg = FakeMessage(text="每天 08:30 500101001 普通")
        await bot.text_handler(msg)
        text = msg.answer.call_args[0][0]
        assert "普通" in text

    @pytest.mark.asyncio
    async def test_nlp_no_station_id(self, bot):
        msg = FakeMessage(text="每天 08:30 沒有站點ID")
        await bot.text_handler(msg)
        text = msg.answer.call_args[0][0]
        # Should find stations by text, or fall through

    @pytest.mark.asyncio
    async def test_command_like_text_fallthrough(self, bot):
        msg = FakeMessage(text="/unknown_command")
        await bot.text_handler(msg)
        text = msg.answer.call_args[0][0]
        assert "抱歉" in text or "help" in text.lower() or "指令" in text


# ── _find_stations ───────────────────────────────────────────

class TestFindStations:
    @pytest.mark.asyncio
    async def test_id_match(self, bot):
        matches = await bot._find_stations("500101001")
        assert len(matches) == 1
        assert matches[0].sno == "500101001"

    @pytest.mark.asyncio
    async def test_name_match(self, bot):
        matches = await bot._find_stations("中山")
        assert len(matches) == 1

    @pytest.mark.asyncio
    async def test_address_match(self, bot):
        matches = await bot._find_stations("大安區")
        assert len(matches) > 0

    @pytest.mark.asyncio
    async def test_no_match(self, bot):
        matches = await bot._find_stations("不存在999")
        assert len(matches) == 0

    @pytest.mark.asyncio
    async def test_empty_cache(self, bot):
        bot.station_service.get_stations = AsyncMock(return_value=[])
        matches = await bot._find_stations("any")
        assert matches == []

    @pytest.mark.asyncio
    async def test_id_no_match_falls_to_fuzzy(self, bot):
        """A long digit that doesn't match by ID should still try fuzzy."""
        matches = await bot._find_stations("999999999")
        assert len(matches) == 0


# ── _check_and_cancel_pending ────────────────────────────────

class TestCheckAndCancelPending:
    @pytest.mark.asyncio
    async def test_cancels_existing(self, bot):
        bot._last_search_results["12345"] = {"command": "query"}
        msg = FakeMessage()
        await bot._check_and_cancel_pending(msg)
        assert "12345" not in bot._last_search_results
        text = msg.answer.call_args[0][0]
        assert "取消" in text

    @pytest.mark.asyncio
    async def test_no_pending_does_nothing(self, bot):
        msg = FakeMessage()
        await bot._check_and_cancel_pending(msg)
        msg.answer.assert_not_called()
