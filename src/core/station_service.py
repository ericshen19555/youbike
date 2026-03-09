import logging
from datetime import datetime
from typing import List, Optional
from src.database.manager import DatabaseManager
from src.api.client import YouBikeClient
from src.models.schemas import StationInfo

class StationService:
    def __init__(self, db_manager: DatabaseManager, api_client: YouBikeClient):
        self.db_manager = db_manager
        self.api_client = api_client
        self._memory_cache: List[StationInfo] = []
        self._last_refresh: Optional[datetime] = None

    async def get_stations(self, force_refresh: bool = False) -> List[StationInfo]:
        """
        Get all station metadata. Tries memory -> database -> API.
        Refreshes from API if data is older than 24 hours or forced.
        """
        now = datetime.now()
        
        # 1. Check Memory Cache
        if self._memory_cache and self._last_refresh and not force_refresh:
            if (now - self._last_refresh).total_seconds() < 3600: # Brief memory cache (1h)
                return self._memory_cache

        # 2. Check Database
        db_stations = self.db_manager.get_stations()
        last_sync_str = self.db_manager.get_meta("last_station_sync")
        
        needs_api_sync = False
        if not db_stations or not last_sync_str or force_refresh:
            needs_api_sync = True
        else:
            try:
                last_sync = datetime.fromisoformat(last_sync_str)
                if (now - last_sync).total_seconds() > 86400: # 24 hours
                    needs_api_sync = True
            except (ValueError, TypeError):
                needs_api_sync = True

        # 3. Fetch from API if needed
        if needs_api_sync:
            logging.info("Station metadata stale or missing. Fetching from YouBike API...")
            api_stations = await self.api_client.fetch_station_list()
            if api_stations:
                self.db_manager.save_stations(api_stations)
                self.db_manager.set_meta("last_station_sync", now.isoformat())
                db_stations = api_stations
                logging.info(f"Successfully synced {len(api_stations)} stations to database.")
            elif not db_stations:
                logging.error("Failed to fetch stations from API and database is empty.")
                return []

        # Update cache
        self._memory_cache = db_stations
        self._last_refresh = now
        return db_stations

    async def find_station_by_id(self, sno: str) -> Optional[StationInfo]:
        stations = await self.get_stations()
        return next((s for s in stations if s.sno == sno), None)
