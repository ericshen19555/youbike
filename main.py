import os
import asyncio
import logging
from dotenv import load_dotenv

from src.api.client import YouBikeClient
from src.database.manager import DatabaseManager
from src.core.user_service import UserService
from src.core.monitor import MonitorEngine
from src.core.scheduler import SchedulerManager
from src.notifiers.telegram import TelegramNotifier

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Load environment variables
load_dotenv()

async def main():
    logging.info("Initializing BikeGuard...")
    
    # 1. Initialize Database
    db_manager = DatabaseManager()
    db_manager.initialize_db()
    
    # 2. Initialize Service Layer
    user_service = UserService(db_manager)
    
    # 3. Initialize API Client
    api_client = YouBikeClient()
    
    # 4. Initialize Notifiers
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    notifiers = []
    if telegram_token and telegram_chat_id:
        notifiers.append(TelegramNotifier(telegram_token, telegram_chat_id))
        logging.info("Telegram Notifier enabled.")
    else:
        logging.warning("Telegram configuration missing. Alerts will only be logged.")

    # 5. Initialize Monitor Engine
    monitor_engine = MonitorEngine(api_client, user_service, notifiers)
    
    # 6. Initialize and Start Scheduler
    # Set interval from ENV or default to 60 seconds
    interval = int(os.getenv("MONITOR_INTERVAL_SECONDS", 60))
    scheduler_manager = SchedulerManager(monitor_engine, interval)
    
    scheduler_manager.start()
    
    logging.info("BikeGuard is running. Press Ctrl+C to stop.")
    
    try:
        # Keep the main loop alive
        while True:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, asyncio.CancelledError):
        logging.info("Shutting down BikeGuard...")
        scheduler_manager.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

