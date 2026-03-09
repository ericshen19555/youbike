import asyncio
import logging
from datetime import datetime
from typing import List, Dict
from src.api.client import YouBikeClient
from src.models.schemas import StationInfo
from src.core.user_service import UserService
from src.notifiers.base import BaseNotifier

class MonitorEngine:
    def __init__(self, api_client: YouBikeClient, user_service: UserService, notifiers: List[BaseNotifier]):
        self.api_client = api_client
        self.user_service = user_service
        self.notifiers = notifiers

    def _is_in_time_window(self, start_str: str, end_str: str, days_str: str) -> bool:
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        current_day = str(now.isoweekday()) # 1 for Monday

        if current_day not in days_str.split(","):
            return False
            
        return start_str <= current_time <= end_str

    async def run_once(self):
        """Execute one check cycle for all active user triggers."""
        # 1. Get active triggers from DB
        triggers = self.user_service.get_active_tasks()
        if not triggers:
            return

        # 2. Extract station IDs to fetch real-time info
        station_ids = list(set([t['station_id'] for t in triggers]))
        
        # 3. Fetch real-time YouBike status (Batch)
        try:
            # We fetch in batches of 20 as suggested by the JS code
            all_realtime_data = {}
            for i in range(0, len(station_ids), 20):
                batch = station_ids[i:i+20]
                realtime_data = await self.api_client.fetch_parking_info(batch)
                all_realtime_data.update(realtime_data)
        except Exception as e:
            logging.error(f"Error fetching real-time data: {e}")
            return

        # 4. Fetch metadata if needed (sna, etc.)
        # Ideally we cache this, but for now we fetch it if not locally available
        # or we could just use the IDs and only fetch metadata for those we notify about.
        stations_list = await self.api_client.fetch_station_list()
        station_metadata = {s.sno: s for s in stations_list}

        # 5. Process each trigger
        for trigger in triggers:
            # Check time window
            if not self._is_in_time_window(trigger['start_time'], trigger['end_time'], trigger['days_of_week']):
                continue

            station_id = trigger['station_id']
            if station_id not in all_realtime_data:
                continue

            realtime = all_realtime_data[station_id]
            bike_type = trigger.get('bike_type', 'any')
            
            if bike_type == 'normal':
                current_count = realtime['sbi_20']
                type_label = "2.0 (普通)"
            elif bike_type == 'electric':
                current_count = realtime['sbi_20e']
                type_label = "2.0E (電輔)"
            else: # 'any'
                current_count = realtime['sbi']
                type_label = "總計 (含電輔)"
            
            # Check threshold (current_count <= threshold)
            if current_count <= trigger['threshold']:
                # Trigger alert
                sna = station_metadata.get(station_id, StationInfo(sno=station_id, sna=station_id)).sna
                message = (
                    f"🚨 *BikeGuard 警戒通知*\n"
                    f"站點：{sna}\n"
                    f"監控對象：*{type_label}*\n"
                    f"目前車輛：*{current_count}*\n"
                    f"(細分: 2.0: {realtime['sbi_20']} / 電輔: {realtime['sbi_20e']})\n"
                    f"空位數：{realtime['bemp']}\n"
                    f"門檻值：{trigger['threshold']}\n"
                    f"建議出發時間：立即出發！"
                )

                
                # Send to notifiers (Note: user_id could be used to route specialized notifications)
                for notifier in self.notifiers:
                    await notifier.send_notification(message)
                    # Note: Simplified. Ideally, specific users get specific notifications.
                    # For Telegram, the bot might have one chat_id per user.

    async def start_loop(self, interval: int = 60):
        while True:
            await self.run_once()
            await asyncio.sleep(interval)
