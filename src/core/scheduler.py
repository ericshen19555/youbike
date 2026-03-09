import logging
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from src.core.monitor import MonitorEngine

class SchedulerManager:
    def __init__(self, monitor_engine: MonitorEngine, interval_seconds: int = 60):
        self.scheduler = AsyncIOScheduler()
        self.monitor_engine = monitor_engine
        self.interval_seconds = interval_seconds

    def start(self):
        """Start the background scheduler."""
        logging.info(f"Starting scheduler with interval: {self.interval_seconds}s")
        self.scheduler.add_job(
            self.monitor_engine.run_once,
            'interval',
            seconds=self.interval_seconds,
            id='youbike_monitor'
        )
        self.scheduler.start()

    def stop(self):
        """Stop the background scheduler."""
        self.scheduler.shutdown()
