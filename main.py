import os
import asyncio
import logging
from dotenv import load_dotenv

from src.api.client import YouBikeClient
from src.database.manager import DatabaseManager
from src.core.user_service import UserService
from src.core.monitor import MonitorEngine
from src.core.scheduler import RRuleScheduler
from src.notifiers.telegram import TelegramNotifier
from src.notifiers.bot import BikeGuardBot


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Load environment variables
load_dotenv()

async def worker_loop(monitor_engine: MonitorEngine, interval: int = 30):
    logging.info(f"Starting Worker loop (Layer 2, interval: {interval}s)")
    while True:
        try:
            await monitor_engine.run_worker_cycle()
        except Exception as e:
            logging.error(f"Error in Worker loop: {e}")
        await asyncio.sleep(interval)

async def main():
    logging.info("Initializing BikeGuard v2 (3-Layer Architecture)...")
    
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
    # 5. Initialize Layers
    monitor_engine = MonitorEngine(api_client, user_service, notifiers)
    rrule_scheduler = RRuleScheduler(db_manager)
    
    # 6. Initialize Bot (Layer 3)
    if telegram_token:
        bot = BikeGuardBot(telegram_token, user_service)
        bot_task = bot.start()
    else:
        bot_task = asyncio.sleep(0) # No-op
    
    # 7. Start Loops
    # Layer 1: Scheduler (Check for new tasks every 60s)
    # Layer 2: Worker (Check due tasks every 15-30s)
    worker_interval = int(os.getenv("WORKER_CHECK_INTERVAL", 15))
    
    try:
        logging.info("BikeGuard is running. Press Ctrl+C to stop.")
        await asyncio.gather(
            rrule_scheduler.start_loop(interval=60),
            worker_loop(monitor_engine, interval=worker_interval),
            bot_task
        )

    except (KeyboardInterrupt, asyncio.CancelledError):
        logging.info("Shutting down BikeGuard...")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass


