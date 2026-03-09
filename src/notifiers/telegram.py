import httpx
import logging
from .base import BaseNotifier

class TelegramNotifier(BaseNotifier):
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{token}/sendMessage"

    async def send_notification(self, message: str, **kwargs):
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(self.api_url, json=payload)
                response.raise_for_status()
                return True
            except Exception as e:
                logging.error(f"Failed to send Telegram notification: {e}")
                return False
