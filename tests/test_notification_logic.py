import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock
from src.core.monitor import MonitorEngine
from src.models.schemas import StationInfo

@pytest.mark.asyncio
async def test_monitor_cooldown_logic():
    # Setup mocks
    api_client = MagicMock()
    user_service = MagicMock()
    station_service = MagicMock()
    notifier = AsyncMock()
    
    # Mock return values for triggered state
    # Station 001 has 1 bike, threshold 3
    api_client.fetch_parking_info = AsyncMock(return_value={
        "001": {"sbi_20": 1, "sbi_20e": 0, "sbi": 1, "bemp": 10, "updatetime": "2026-04-13 11:30:00"}
    })
    station_service.get_stations = AsyncMock(return_value=[
        StationInfo(sno="001", sna="Test Station", tot=20)
    ])
    
    # Task that was notified 1 minute ago
    last_notified = (datetime.now() - timedelta(minutes=1)).isoformat()
    user_service.db.get_pending_tasks = MagicMock(return_value=[
        {
            "id": 1, "sub_id": 10, "station_id": "001", "bike_type": "normal", 
            "threshold": 3, "user_id": "user123", "last_notified_at": last_notified
        }
    ])
    
    engine = MonitorEngine(api_client, user_service, station_service, [notifier])
    
    # Run cycle
    await engine.run_worker_cycle()
    
    # Verify: Notifier should NOT be called due to cooldown
    notifier.send_notification.assert_not_called()
    
    # Task that was notified 11 minutes ago
    last_notified_old = (datetime.now() - timedelta(minutes=11)).isoformat()
    user_service.db.get_pending_tasks = MagicMock(return_value=[
        {
            "id": 2, "sub_id": 11, "station_id": "001", "bike_type": "normal", 
            "threshold": 3, "user_id": "user123", "last_notified_at": last_notified_old
        }
    ])
    
    # Run cycle again
    await engine.run_worker_cycle()
    
    # Verify: Notifier SHOULD be called now
    notifier.send_notification.assert_called_once()

@pytest.mark.asyncio
async def test_monitor_warning_when_no_notifiers(caplog):
    api_client = AsyncMock()
    user_service = MagicMock()
    station_service = AsyncMock()
    
    api_client.fetch_parking_info.return_value = {
        "001": {"sbi_20": 1, "sbi_20e": 0, "sbi": 1, "bemp": 10, "updatetime": "2026-04-13 11:30:00"}
    }
    station_service.get_stations.return_value = [
        StationInfo(sno="001", sna="Test Station", tot=20)
    ]
    user_service.db.get_pending_tasks.return_value = [
        {
            "id": 3, "sub_id": 12, "station_id": "001", "bike_type": "normal", 
            "threshold": 3, "user_id": "user123", "last_notified_at": None
        }
    ]
    
    # Empty notifiers
    engine = MonitorEngine(api_client, user_service, station_service, [])
    
    import logging
    with caplog.at_level(logging.WARNING):
        await engine.run_worker_cycle()
        
    assert "no notification channels (notifiers) are configured" in caplog.text
