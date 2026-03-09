"""Tests for src/models/schemas.py — all three Pydantic models."""
from src.models.schemas import StationInfo, UserSubscription, ActiveTask


class TestStationInfo:
    def test_defaults(self):
        s = StationInfo(sno="001", sna="A站")
        assert s.sno == "001"
        assert s.sna == "A站"
        assert s.tot == 0
        assert s.sbi == 0
        assert s.sbi_20 == 0
        assert s.sbi_20e == 0
        assert s.lat == 0.0
        assert s.lng == 0.0
        assert s.ar is None
        assert s.sarea is None
        assert s.sareaen is None
        assert s.bemp == 0
        assert s.updatetime == ""
        assert s.act == "1"
        assert s.isRealtime is False

    def test_full_values(self):
        s = StationInfo(
            sno="500101001", sna="科技大樓", tot=30, sbi=10,
            sbi_20=6, sbi_20e=4, lat=25.0, lng=121.5,
            ar="addr", sarea="area", sareaen="areaen",
            bemp=20, updatetime="2026-01-01", act="0", isRealtime=True,
        )
        assert s.tot == 30
        assert s.isRealtime is True
        assert s.act == "0"


class TestUserSubscription:
    def test_defaults(self):
        u = UserSubscription(user_id="u1", station_id="s1", rrule="FREQ=DAILY")
        assert u.id is None
        assert u.threshold == 3
        assert u.bike_type == "any"
        assert u.is_active is True

    def test_custom_values(self):
        u = UserSubscription(
            id=5, user_id="u1", station_id="s1",
            rrule="ONCE:2026-01-01T00:00:00",
            threshold=10, bike_type="electric", is_active=False,
        )
        assert u.id == 5
        assert u.bike_type == "electric"
        assert u.is_active is False


class TestActiveTask:
    def test_defaults(self):
        t = ActiveTask(sub_id=1, next_run="2026-01-01T00:00:00")
        assert t.id is None
        assert t.current_interval == 60
        assert t.status == "pending"

    def test_custom(self):
        t = ActiveTask(id=2, sub_id=1, next_run="x", current_interval=15, status="running")
        assert t.current_interval == 15
        assert t.status == "running"
