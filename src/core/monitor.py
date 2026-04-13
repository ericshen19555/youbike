import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict
from src.api.client import YouBikeClient
from src.models.schemas import StationInfo
from src.config.constants import (
    DYNAMIC_INTERVAL_HIGH, 
    DYNAMIC_INTERVAL_MEDIUM, 
    DYNAMIC_INTERVAL_LOW,
    NOTIFICATION_COOLDOWN_SECONDS
)
from src.core.user_service import UserService
from src.core.station_service import StationService
from src.notifiers.base import BaseNotifier

class MonitorEngine:
    def __init__(self, api_client: YouBikeClient, user_service: UserService, station_service: StationService, notifiers: List[BaseNotifier]):
        self.api_client = api_client
        self.user_service = user_service
        self.station_service = station_service
        self.notifiers = notifiers


    async def run_once(self):
        """Execute one check cycle for all active user triggers."""
    async def run_worker_cycle(self):
        """
        Layer 2: Worker execution cycle.
        1. Fetch due tasks from DB.
        2. Batch station requests.
        3. Check thresholds and alert.
        4. Update next_run based on dynamic interval or retire task.
        """
        now = datetime.now()
        now_iso = now.isoformat()
        tasks = self.user_service.db.get_pending_tasks(now_iso)
        
        if not tasks:
            return

        # 1. Gather all unique station IDs for batching
        station_ids = list(set(t['station_id'] for t in tasks))
        
        # 2. Fetch metadata from StationService (Cached/DB)
        stations = await self.station_service.get_stations()
        station_metadata = {s.sno: s for s in stations}
        
        # 3. Batch fetch real-time parking info
        all_realtime_data = {}
        for i in range(0, len(station_ids), 20):
            batch = station_ids[i:i+20]
            batch_data = await self.api_client.fetch_parking_info(batch)
            all_realtime_data.update(batch_data)

        # 4. Process each task
        for task in tasks:
            task_id = task['id']
            station_id = task['station_id']
            target_time_str = task.get('target_time')
            
            # Retirement Check: If more than 10 mins past target time, retire task
            if target_time_str:
                try:
                    target_dt = datetime.fromisoformat(target_time_str)
                    if now > target_dt + timedelta(minutes=10):
                        logging.info(f"Task {task_id} (sub {task['sub_id']}) monitoring window closed (Target was {target_time_str}). Retiring task.")
                        self.user_service.db.update_task_status(task_id, status='completed')
                        continue
                except (ValueError, TypeError):
                    pass

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
            notification_sent = False
            if is_triggered:
                # Cooldown check:
                should_notify = True
                last_notify_str = task.get('last_notified_at')
                if last_notify_str:
                    try:
                        last_notify = datetime.fromisoformat(last_notify_str)
                        if (datetime.now() - last_notify).total_seconds() < NOTIFICATION_COOLDOWN_SECONDS:
                            should_notify = False
                            logging.info(f"Notification suppressed for station {station_id} (sub {task['sub_id']}) due to cooldown.")
                    except (ValueError, TypeError):
                        pass

                if should_notify:
                    if not self.notifiers:
                        logging.warning(f"Alert triggered for station {station_id} (sub {task['sub_id']}), but no notification channels (notifiers) are configured.")
                    else:
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
                            success = await notifier.send_notification(message, chat_id=task['user_id'])
                            if success:
                                notification_sent = True
                                logging.info(f"[NOTIFY] Successfully alerted user for station '{sna}' ({current_count} {type_label} bikes left)")

            # 5. Schedule next run or DELETE if one-time
            if is_triggered and task.get('rrule', '').startswith('ONCE:'):
                if notification_sent:
                    logging.info(f"One-time task {task_id} (sub {task['sub_id']}) completed notification. Deleting subscription.")
                    self.user_service.remove_subscription_by_id(task['sub_id'])
                else:
                    # If it's a ONCE task but we haven't successfully notified yet, 
                    # we keep it alive but with high frequency.
                    next_run_dt = datetime.now() + timedelta(seconds=new_interval)
                    self.user_service.db.update_task_status(
                        task_id, 
                        status='pending', 
                        next_run=next_run_dt.isoformat(), 
                        interval=new_interval
                    )
            else:
                next_run_dt = datetime.now() + timedelta(seconds=new_interval)
                last_notified = datetime.now().isoformat() if notification_sent else task.get('last_notified_at')
                self.user_service.db.update_task_status(
                    task_id, 
                    status='pending', 
                    next_run=next_run_dt.isoformat(), 
                    interval=new_interval,
                    last_notified_at=last_notified
                )

    async def run_once(self):
        """
        [LEGACY] Execute one check cycle for all active user triggers.
        This method is kept for backward compatibility. Use run_worker_cycle instead.
        """
        await self.run_worker_cycle()

    async def start_loop(self, interval: int = 60):
        while True:
            await self.run_once()
            await asyncio.sleep(interval)
