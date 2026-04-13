import asyncio
import logging
from datetime import datetime, timedelta
from src.database.manager import DatabaseManager
from src.models.schemas import ActiveTask
from src.config.constants import SCHEDULER_CHECK_INTERVAL, PRE_MONITOR_LEAD_TIME_MINUTES
from src.utils.rrule_utils import get_next_occurrence


class RRuleScheduler:
    """
    Layer 1: Scheduler.
    Populates active_tasks from user_subscriptions based on RRule.
    """
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    async def run_scheduler_cycle(self):
        """
        Check all active subscriptions and ensure they have a pending task 
        scheduled for their next occurrence.
        """
        subs = self.db.get_all_active_subscriptions()
        
        for sub in subs:
            sub_id = sub['id']
            rrule_str = sub['rrule']
            
            # Check if this sub already has a pending task
            pending_tasks = self.db.get_tasks_for_subscription(sub_id, status='pending')
            
            if not pending_tasks:
                # Calculate next occurrence
                base_next_run = get_next_occurrence(rrule_str)
                if base_next_run:
                    # Shift back by lead time
                    next_run = base_next_run - timedelta(minutes=PRE_MONITOR_LEAD_TIME_MINUTES)
                    
                    # If the shifted time is already in the past, get the next occurrence's shifted time
                    # or just use it if it's very recent. 
                    # For safety, if next_run < now, we might want to skip or start immediately.
                    if next_run < datetime.now():
                        # Option A: Start now if we are within the lead time window
                        # Option B: Re-calculate for the next occurrence if we missed the window
                        # Let's go with Option A: Start now to be helpful
                        next_run = datetime.now()

                    task = ActiveTask(
                        sub_id=sub_id,
                        next_run=next_run.isoformat(),
                        target_time=base_next_run.isoformat(),
                        current_interval=60, 
                        status='pending'
                    )
                    self.db.add_task(task)
                    logging.info(f"Scheduled lead-time run for sub {sub_id} at {next_run.isoformat()} (Target: {base_next_run})")



    async def start_loop(self, interval: int = SCHEDULER_CHECK_INTERVAL):
        logging.info(f"Starting RRuleScheduler loop (interval: {interval}s)")

        while True:
            try:
                await self.run_scheduler_cycle()
            except Exception as e:
                logging.error(f"Error in RRuleScheduler loop: {e}")
            await asyncio.sleep(interval)
