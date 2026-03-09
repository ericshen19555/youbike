import asyncio
import sys
import os

# Ensure the root directory is in the python path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from src.database.manager import DatabaseManager
from src.core.user_service import UserService
from src.core.monitor import MonitorEngine
from src.api.client import YouBikeClient

async def test_bike_filtering():
    db_manager = DatabaseManager("test_filter.db")
    db_manager.initialize_db()
    
    user_service = UserService(db_manager)
    api_client = YouBikeClient()
    
    # Add triggers for different bike types
    # Station 500101001 (MRT Technology Bldg)
    user_id = "test_user"
    station_id = "500101001"
    
    print("Setting up test triggers...")
    # Trigger 1: Any bike (Total)
    await user_service.register_trigger(user_id, station_id, threshold=10, 
                                       start_time="00:00", end_time="23:59", days_of_week="1,2,3,4,5,6,7",
                                       bike_type="any")
    
    # Trigger 2: Only Normal
    await user_service.register_trigger(user_id, station_id, threshold=5, 
                                       start_time="00:00", end_time="23:59", days_of_week="1,2,3,4,5,6,7",
                                       bike_type="normal")
    
    # Trigger 3: Only Electric
    await user_service.register_trigger(user_id, station_id, threshold=2, 
                                       start_time="00:00", end_time="23:59", days_of_week="1,2,3,4,5,6,7",
                                       bike_type="electric")
    
    print("Triggers registered. Running MonitorEngine.run_once()...")
    
    # Mock notifier to see output
    class MockNotifier:
        async def send_notification(self, message: str):
            print(f"\n[NOTIFY]\n{message}\n")
            
    monitor = MonitorEngine(api_client, user_service, [MockNotifier()])
    await monitor.run_once()
    
    # Clean up test DB
    if os.path.exists("test_filter.db"):
        os.remove("test_filter.db")

if __name__ == "__main__":
    asyncio.run(test_bike_filtering())
