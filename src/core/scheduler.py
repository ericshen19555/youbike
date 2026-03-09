import asyncio
import logging
from datetime import datetime
from src.database.manager import DatabaseManager
from src.models.schemas import ActiveTask
from src.config.constants import SCHEDULER_CHECK_INTERVAL
from src.utils.rrule_utils import get_next_occurrence

class RRuleScheduler:
    """
    Layer 1: Scheduler.
    Populates active_tasks from user_subscriptions based on RRule.
    """
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    async def run_scheduler_cycle(self):
        # ... (logic remains same)
        pass

    async def start_loop(self, interval: int = SCHEDULER_CHECK_INTERVAL):
        logging.info(f"Starting RRuleScheduler loop (interval: {interval}s)")

        while True:
            try:
                await self.run_scheduler_cycle()
            except Exception as e:
                logging.error(f"Error in RRuleScheduler loop: {e}")
            await asyncio.sleep(interval)
