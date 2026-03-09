"""
Shared fixtures for the BikeGuard test suite.
All external I/O (Telegram API, YouBike API, file-system DB) is mocked here
so the tests run offline, fast, and deterministically.
"""
import os, sys, sqlite3, asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure project root is on sys.path so `src.*` imports work
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.database.manager import DatabaseManager
from src.core.user_service import UserService
from src.core.station_service import StationService
from src.api.client import YouBikeClient
from src.models.schemas import StationInfo, UserSubscription, ActiveTask


# ── helpers ──────────────────────────────────────────────────

def make_station(**overrides) -> StationInfo:
    defaults = dict(
        sno="500101001", sna="測試站A", tot=30, sbi=10, sbi_20=6, sbi_20e=4,
        lat=25.033, lng=121.565, ar="台北市大安區", sarea="大安區", sareaen="Daan",
        bemp=20, updatetime="2026-01-01 12:00:00", act="1",
    )
    defaults.update(overrides)
    return StationInfo(**defaults)


SAMPLE_STATIONS = [
    make_station(sno="500101001", sna="科技大樓"),
    make_station(sno="500101002", sna="科技園區"),
    make_station(sno="500102003", sna="中山國小"),
]


# ── fixtures ─────────────────────────────────────────────────

@pytest.fixture
def tmp_db(tmp_path):
    """Return a DatabaseManager backed by a temp SQLite file."""
    db_path = str(tmp_path / "test.db")
    dm = DatabaseManager(db_path)
    dm.initialize_db()
    return dm


@pytest.fixture
def user_service(tmp_db):
    return UserService(tmp_db)


@pytest.fixture
def mock_api_client():
    client = MagicMock(spec=YouBikeClient)
    client.fetch_station_list = AsyncMock(return_value=SAMPLE_STATIONS)
    client.fetch_parking_info = AsyncMock(return_value={
        "500101001": {
            "tot": 30, "sbi": 10, "sbi_20": 6, "sbi_20e": 4,
            "bemp": 20, "updatetime": "2026-01-01 12:00:00", "isRealtime": True,
        }
    })
    return client


@pytest.fixture
def station_service(tmp_db, mock_api_client):
    return StationService(tmp_db, mock_api_client)


# ── Fake aiogram objects ─────────────────────────────────────

class FakeChat:
    def __init__(self, chat_id=12345):
        self.id = chat_id


class FakeLocation:
    def __init__(self, lat=25.033, lng=121.565):
        self.latitude = lat
        self.longitude = lng


class FakeMessage:
    """Minimal stand-in for aiogram.types.Message."""
    def __init__(self, text="", chat_id=12345, location=None):
        self.text = text
        self.chat = FakeChat(chat_id)
        self.location = location
        self.answer = AsyncMock()
