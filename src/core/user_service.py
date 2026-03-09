from src.database.manager import DatabaseManager
from src.models.schemas import UserSubscription
from typing import List

class UserService:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    async def register_subscription(self, user_id: str, station_id: str, threshold: int, 
                                 rrule: str, bike_type: str = "any"):
        """
        Register or update a long-term monitoring subscription.
        """
        sub = UserSubscription(
            user_id=user_id,
            station_id=station_id,
            rrule=rrule,
            threshold=threshold,
            bike_type=bike_type
        )
        sub_id = self.db.add_or_update_subscription(sub)
        return sub_id

    def get_subscriptions(self, user_id: str) -> List[dict]:
        return self.db.get_user_subscriptions(user_id)

    def remove_subscription(self, user_id: str, station_id: str):
        # We'd need to add a delete_subscription method to DB manager
        pass


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
