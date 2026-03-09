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
        self.db.delete_subscription(user_id, station_id)
        return True

    def clear_all_subscriptions(self, user_id: str):
        self.db.delete_all_user_subscriptions(user_id)
        return True

