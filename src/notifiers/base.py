from abc import ABC, abstractmethod

class BaseNotifier(ABC):
    @abstractmethod
    async def send_notification(self, message: str, **kwargs):
        """
        Abstract method to send notification to the user.
        Must be implemented by subclasses (e.g., TelegramNotifier).
        """
        ...
