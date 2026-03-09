from abc import ABC, abstractmethod

class BaseNotifier(ABC):
    @abstractmethod
    async def send_notification(self, message: str, **kwargs):
        pass
