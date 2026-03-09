import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict
from src.api.client import YouBikeClient
from src.models.schemas import StationInfo
from src.config.constants import DYNAMIC_INTERVAL_HIGH, DYNAMIC_INTERVAL_MEDIUM, DYNAMIC_INTERVAL_LOW
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
    async def run_worker_cycle(self):
        """
        Layer 2: Worker execution cycle.
        1. Fetch due tasks from DB.
        2. Batch station requests.
        3. Check thresholds and alert.
        4. Update next_run based on dynamic interval.
        """
        now_iso = datetime.now().isoformat()
        tasks = self.user_service.db.get_pending_tasks(now_iso)
        
        if not tasks:
            return

        # 1. Gather all unique station IDs for batching
        station_ids = list(set(t['station_id'] for t in tasks))
        
        # 2. Fetch metadata (can be cached in a real app, but here we fetch once per cycle)
        # Note: fetch_station_list is expensive, maybe we should cache it in self.
        station_metadata = {s.sno: s for s in await self.api_client.fetch_station_list()}
        
        # 3. Batch fetch real-time parking info (max 20 per request is good)
        all_realtime_data = {}
        for i in range(0, len(station_ids), 20):
            batch = station_ids[i:i+20]
            batch_data = await self.api_client.fetch_parking_info(batch)
            all_realtime_data.update(batch_data)

        # 4. Process each task
        for task in tasks:
            task_id = task['id']
            station_id = task['station_id']
            
            if station_id not in all_realtime_data:
                continue

            realtime = all_realtime_data[station_id]
            bike_type = task['bike_type'] or 'any'
            threshold = task['threshold']
            
            if bike_type == 'normal':
                current_count = realtime['sbi_20']
                type_label = "2.0 (普通)"
            elif bike_type == 'electric':
                current_count = realtime['sbi_20e']
                type_label = "2.0E (電輔)"
            else: # 'any'
                current_count = realtime['sbi']
                type_label = "總計 (含電輔)"
            
            # Determine new interval (Dynamic Frequency)
            new_interval = DYNAMIC_INTERVAL_LOW
            is_triggered = False
            
            if current_count <= threshold:
                new_interval = DYNAMIC_INTERVAL_HIGH
                is_triggered = True
            elif current_count <= threshold * 2:
                new_interval = DYNAMIC_INTERVAL_MEDIUM

            
            # If triggered, notify
            if is_triggered:
                sna = station_metadata.get(station_id, StationInfo(sno=station_id, sna=station_id)).sna
                message = (
                    f"🚨 *BikeGuard 警戒通知*\n"
                    f"站點：{sna}\n"
                    f"監控對象：*{type_label}*\n"
                    f"目前車輛：*{current_count}* (低於門檻 {threshold})\n"
                    f"(細分: 2.0: {realtime['sbi_20']} / 電輔: {realtime['sbi_20e']})\n"
                    f"空位數：{realtime['bemp']}\n"
                    f"更新時間：{realtime['updatetime']}\n"
                    f"建議出發時間：立即出發！"
                )
                for notifier in self.notifiers:
                    await notifier.send_notification(message, chat_id=task['user_id'])


            # 5. Schedule next run
            next_run_dt = datetime.now() + timedelta(seconds=new_interval)
            
            # Note: We should verify if the task's monitoring window is still open.
            # For this MVP, let's keep it running for 60 minutes after start.
            # (In a full implementation, we'd check against a 'stop' condition or duration)
            self.user_service.db.update_task_status(
                task_id, 
                status='pending', 
                next_run=next_run_dt.isoformat(), 
                interval=new_interval
            )

    async def run_once(self):
        """Legacy method for backward compatibility/quick tests."""
        await self.run_worker_cycle()

    async def start_loop(self, interval: int = 60):
        while True:
            await self.run_once()
            await asyncio.sleep(interval)
