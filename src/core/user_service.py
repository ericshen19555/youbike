from src.database.manager import DatabaseManager
from src.models.schemas import UserTrigger
from typing import List

class UserService:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    async def register_trigger(self, user_id: str, station_id: str, threshold: int, 
                               start_time: str, end_time: str, days_of_week: str,
                               bike_type: str = "any"):
        """
        Interface for Telegram Bot to add/update tracking settings.
        """
        trigger = UserTrigger(
            user_id=user_id,
            station_id=station_id,
            threshold=threshold,
            start_time=start_time,
            end_time=end_time,
            days_of_week=days_of_week,
            bike_type=bike_type
        )
        self.db.add_or_update_trigger(trigger)
        return True

    def remove_tracking(self, user_id: str, station_id: str):
        self.db.delete_trigger(user_id, station_id)
        return True

    def list_user_trackings(self, user_id: str) -> List[dict]:
        return self.db.get_user_triggers(user_id)

    def get_active_tasks(self) -> List[dict]:
        """
        Returns all active triggers for the monitoring engine.
        """
        return self.db.get_all_active_triggers()
