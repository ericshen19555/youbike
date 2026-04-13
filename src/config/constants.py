import os
from dotenv import load_dotenv

load_dotenv()

# --- API URLs ---
# metadata
YB2_STATION_LIST_URL = "https://apis.youbike.com.tw/json/station-min-yb2.json"
# real-time parking info (POST)
YB2_PARKING_INFO_URL = "https://apis.youbike.com.tw/tw2/parkingInfo"

# --- Bot Configuration ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# --- Monitoring Defaults ---
DEFAULT_THRESHOLD = 3
DYNAMIC_INTERVAL_HIGH = 15
DYNAMIC_INTERVAL_MEDIUM = 30
DYNAMIC_INTERVAL_LOW = 60

# --- Monitoring Timing ---
PRE_MONITOR_LEAD_TIME_MINUTES = 20 # Start monitoring 20 minutes before the target time
SCHEDULER_CHECK_INTERVAL = 60
WORKER_CHECK_INTERVAL = int(os.getenv("WORKER_CHECK_INTERVAL", 15))

# --- Notification Policy ---
NOTIFICATION_COOLDOWN_SECONDS = 300 # 5 minutes

