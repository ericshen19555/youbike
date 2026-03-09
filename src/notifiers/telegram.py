import httpx
import logging
from typing import Optional
from .base import BaseNotifier

class TelegramNotifier(BaseNotifier):
    def __init__(self, token: str, default_chat_id: Optional[str] = None):
        self.token = token
        self.default_chat_id = default_chat_id
        self.api_url = f"https://api.telegram.org/bot{token}/sendMessage"

    async def send_notification(self, message: str, chat_id: Optional[str] = None, **kwargs):
        target_chat_id = chat_id or self.default_chat_id
        if not target_chat_id:
            logging.error("No chat_id provided for Telegram notification.")
            return False
            
        payload = {
            "chat_id": target_chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(self.api_url, json=payload)
                response.raise_for_status()
                return True
            except Exception as e:
                logging.error(f"Failed to send Telegram notification to {target_chat_id}: {e}")
                return False

