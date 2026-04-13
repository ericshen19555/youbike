"""Tests for src/utils/rrule_utils.py — get_next_occurrence and is_rrule_active_now."""
from datetime import datetime, timedelta
from src.utils.rrule_utils import get_next_occurrence, is_rrule_active_now


class TestGetNextOccurrence:
    # ── ONCE format ──
    def test_once_future(self):
        future = (datetime.now() + timedelta(hours=1)).isoformat()
        result = get_next_occurrence(f"ONCE:{future}")
        assert result is not None
        assert result > datetime.now() - timedelta(seconds=5)

    def test_once_past_returns_none(self):
        past = (datetime.now() - timedelta(hours=1)).isoformat()
        assert get_next_occurrence(f"ONCE:{past}") is None

    def test_once_invalid_iso_returns_none(self):
        assert get_next_occurrence("ONCE:not-a-date") is None

    def test_once_with_explicit_after_dt(self):
        target = datetime(2026, 6, 15, 10, 0)
        after = datetime(2026, 6, 15, 9, 0)
        result = get_next_occurrence(f"ONCE:{target.isoformat()}", after_dt=after)
        assert result == target

    def test_once_with_after_dt_past(self):
        target = datetime(2026, 6, 15, 10, 0)
        after = datetime(2026, 6, 15, 11, 0)
        assert get_next_occurrence(f"ONCE:{target.isoformat()}", after_dt=after) is None

    # ── Standard RRule ──
    def test_standard_rrule(self):
        rrule = "FREQ=DAILY;BYHOUR=8;BYMINUTE=0"
        after = datetime(2026, 1, 1, 7, 0)
        result = get_next_occurrence(rrule, after_dt=after)
        assert result is not None
        assert result.hour == 8

    def test_invalid_rrule_returns_none(self):
        assert get_next_occurrence("NOT_A_VALID_RRULE") is None

    def test_default_after_dt_is_now(self):
        rrule = "FREQ=DAILY;BYHOUR=23;BYMINUTE=59"
        result = get_next_occurrence(rrule)
        assert result is not None

    # ── is_rrule_active_now (stub that raises NotImplementedError) ──
    def test_is_rrule_active_now_raises_not_implemented(self):
        import pytest
        with pytest.raises(NotImplementedError):
            is_rrule_active_now("FREQ=DAILY")
