import asyncio
import logging
import os
import re
import json
from datetime import datetime
from typing import List, Optional
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message

from src.core.user_service import UserService
from src.utils.nlp_parser import parse_natural_language_to_rrule
from src.config.constants import DEFAULT_THRESHOLD
from src.utils.geo_utils import calculate_distance
from src.api.client import YouBikeClient
from src.models.schemas import StationInfo


class BikeGuardBot:

    def __init__(self, token: str, user_service: UserService, api_client: YouBikeClient):
        self.bot = Bot(token=token)
        self.dp = Dispatcher()
        self.user_service = user_service
        self.api_client = api_client
        self._station_cache: Optional[List[StationInfo]] = None
        self._cache_time: Optional[datetime] = None
        self._last_search_results: dict = {} # user_id -> dict
        self._setup_handlers()

    def _setup_handlers(self):
        self.dp.message.register(self.start_handler, Command("start"))
        self.dp.message.register(self.add_handler, Command("add"))
        self.dp.message.register(self.list_handler, Command("list"))
        self.dp.message.register(self.remove_handler, Command("remove"))
        self.dp.message.register(self.query_handler, Command("query"))
        self.dp.message.register(self.cancel_handler, Command("cancel"))
        self.dp.message.register(self.number_selection_handler, lambda m: m.text.isdigit() and str(m.chat.id) in self._last_search_results)
        self.dp.message.register(self.location_handler, lambda m: m.location is not None)
        self.dp.message.register(self.text_handler) # Catch-all for NLP and search

    async def _get_station_cache(self) -> List[StationInfo]:
        # Cache for 10 minutes
        now = datetime.now()
        should_update = (
            self._station_cache is None or 
            self._cache_time is None or 
            (now - self._cache_time).total_seconds() > 600
        )
        if should_update:
            self._station_cache = await self.api_client.fetch_station_list()
            self._cache_time = now
        return self._station_cache or []


    async def _find_stations(self, query: str) -> List[StationInfo]:
        stations = await self._get_station_cache()
        if not stations:
            return []
            
        # 1. Direct ID match
        if query.isdigit() and len(query) >= 3:
            exact = [s for s in stations if s.sno == query]
            if exact: return exact
            
        # 2. Fuzzy name/address match
        q = query.lower()
        matches = [s for s in stations if q in s.sna.lower() or (s.ar and q in s.ar.lower()) or (s.sarea and q in s.sarea.lower())]
        
        # Sort by name length to get "closer" matches first
        matches.sort(key=lambda x: len(x.sna))
        return matches



    async def start_handler(self, message: Message):
        chat_id = message.chat.id
        logging.info(f"Received /start from user. Chat ID: {chat_id}")
        await message.answer(

            "🚲 *歡迎來到 BikeGuard YouBike 監控系統*\n\n"
            "你可以使用以下指令：\n"
            "/add [站點ID] [門檻值] - 開始追蹤\n"
            "/list - 查看目前的追蹤清單\n"
            "/remove - 移除追蹤\n\n"
            "或者直接輸入如：*『每週五 17:00 科技大樓站 門檻 5』* (開發中)",
            parse_mode="Markdown"
        )

    async def add_handler(self, message: Message):
        # Example: /add [名稱/ID] [門檻值] [時間規則] [車型]
        args = message.text.split()
        if len(args) < 2:
            await message.answer(
                "❌ *格式錯誤*\n請輸入：`/add [站點名稱 或 ID] [門檻值] [時間規則] [車型(可選)]`\n"
                "例如：`/add 科技大樓 3 每天 08:30`",
                parse_mode="Markdown"
            )
            return
            
        target_query = args[1]
        matches = await self._find_stations(target_query)
        
        if not matches:
            await message.answer(f"❓ 找不到任何站點符合『{target_query}』。請換個關鍵字試試。")
            return
            
        if len(matches) > 1:
            self._last_search_results[str(message.chat.id)] = {
                "matches": matches,
                "command": "add",
                "args": args[2:] # Store threshold, time, etc.
            }
            resp = "🧐 *找到多個相似站點，請輸入編號 (1-n) 來選擇：*\n\n"
            for i, s in enumerate(matches, 1):
                resp += f"{i}. 🏠 `{s.sna}` (ID: `{s.sno}`)\n"
            await message.answer(resp, parse_mode="Markdown")
            return
            
        # Exactly one match
        await self._register_sub_with_station(message, matches[0], args[2:])

    async def _register_sub_with_station(self, message: types.Message, station: StationInfo, sub_args: List[str]):
        # sub_args: [threshold, time_rule, bike_type...]
        try:
            threshold = int(sub_args[0]) if len(sub_args) > 0 else DEFAULT_THRESHOLD
        except (ValueError, IndexError):
            threshold = DEFAULT_THRESHOLD
            
        full_text = " ".join(sub_args[1:]) if len(sub_args) > 1 else "每天 00:00"
        
        # 1. Extract bike type
        bike_type = "any"
        if "電輔" in full_text or "電" in full_text:
            bike_type = "electric"
            type_display = "2.0E (電輔)"
        elif "普通" in full_text or "一般" in full_text:
            bike_type = "normal"
            type_display = "2.0 (普通)"
        else:
            type_display = "兩者皆可"
            
        # 2. Extract and parse time
        rrule = parse_natural_language_to_rrule(full_text)
        
        await self.user_service.register_subscription(
            user_id=str(message.chat.id),
            station_id=station.sno,
            threshold=threshold,
            rrule=rrule,
            bike_type=bike_type
        )
        
        await message.answer(
            f"✅ *定時監控已開啟！*\n\n"
            f"📍 站點：`{station.sna}` (ID: `{station.sno}`)\n"
            f"🎯 門檻：{threshold} 輛\n"
            f"🚲 車型：{type_display}\n"
            f"⏰ 規則：{full_text} (`{rrule}`)\n\n"
            f"💡 系統將在指定時間前 **20 分鐘** 開始監控，若車輛過低會即時通知。",
            parse_mode="Markdown"
        )

    async def number_selection_handler(self, message: Message):
        user_id = str(message.chat.id)
        if user_id not in self._last_search_results:
            return
            
        state = self._last_search_results[user_id]
        matches = state.get("matches", [])
        try:
            choice_idx = int(message.text) - 1
            if 0 <= choice_idx < len(matches):
                selected = matches[choice_idx]
                command = state.get("command")
                
                if command == "add":
                    await self._register_sub_with_station(message, selected, state.get("args", []))
                elif command == "remove":
                    self.user_service.remove_subscription(user_id, selected.sno)
                    await message.answer(f"✅ 已成功移除站點 `[{selected.sna}]` 的監控任務。", parse_mode="Markdown")
                elif command == "query":
                    await self._send_detailed_query(message, selected)
                    
                self._last_search_results.pop(user_id, None)
            else:
                await message.answer(f"❌ 請輸入有效編號 (1-{len(matches)})。")
        except (ValueError, KeyError, TypeError):
            pass


    async def query_handler(self, message: Message):
        args = message.text.split()
        if len(args) < 2:
            await message.answer("🔍 請輸入 `/query [站點名稱 或 ID]` 來查詢詳細資訊。")
            return
            
        query = args[1]
        matches = await self._find_stations(query)
        
        if not matches:
            await message.answer(f"❓ 找不到任何站點符合『{query}』。")
            return
            
        if len(matches) > 1:
            self._last_search_results[str(message.chat.id)] = {
                "matches": matches[:10],
                "command": "query",
                "args": []
            }
            resp = "🧐 *找到多個相似站點，請輸入編號來查詢：*\n\n"
            for i, s in enumerate(matches[:10], 1):
                resp += f"{i}. 🏠 `{s.sna}` (ID: `{s.sno}`)\n"
            await message.answer(resp, parse_mode="Markdown")
            return
            
        await self._send_detailed_query(message, matches[0])

    async def _send_detailed_query(self, message: Message, station: StationInfo):
        # Fetch real-time data for this specific station
        realtime_map = await self.api_client.fetch_parking_info([station.sno])
        realtime = realtime_map.get(station.sno, {})
        
        # Format the full station data
        data = {
            "metadata": station.__dict__,
            "realtime": realtime
        }
        
        # Create a formatted output
        formatted_json = json.dumps(data, indent=2, ensure_ascii=False)
        
        resp = (
            f"🔍 *站點詳細資訊：{station.sna}*\n\n"
            f"🔢 站點 ID：`{station.sno}`\n"
            f"📍 區域：{station.sarea} | {station.sareaen}\n"
            f"🏠 地址：{station.ar}\n"
            f"🚲 即時現況：\n"
            f"  - 2.0 普通車：*{realtime.get('sbi_20', 'N/A')}*\n"
            f"  - 2.0E 電輔：*{realtime.get('sbi_20e', 'N/A')}*\n"
            f"  - 空位數：{realtime.get('bemp', 'N/A')}\n"
            f"🕒 最後更新：{realtime.get('updatetime', 'N/A')}\n\n"
            f"📜 *完整資料節錄 (JSON)：*\n"
            f"```json\n"
            f"{formatted_json[:3000]}\n" # Limit to avoid Telegram message limit
            f"```"
        )
        await message.answer(resp, parse_mode="Markdown")



    async def list_handler(self, message: Message):
        subs = self.user_service.get_subscriptions(str(message.chat.id))
        if not subs:
            await message.answer("你目前沒有任何監控任務。使用 `/add` 來新增一個吧！")
            return
            
        stations = await self._get_station_cache()
        station_map = {s.sno: s.sna for s in stations}
        
        text = "📋 *你的監控清單：*\n\n"
        for i, s in enumerate(subs, 1):
            type_map = {"any": "兩者", "normal": "普通", "electric": "電輔"}
            type_label = type_map.get(s['bike_type'], "兩者")
            sna = station_map.get(s['station_id'], s['station_id'])
            text += f"{i}. 🏠 *{sna}* (`{s['station_id']}`)\n   門檻: {s['threshold']} | 車型: {type_label}\n   規則: `{s['rrule']}`\n\n"
        
        text += "💡 使用 `/remove [站點名稱/ID]` 來移除監控。"
        await message.answer(text, parse_mode="Markdown")

    async def remove_handler(self, message: Message):
        args = message.text.split()
        user_id = str(message.chat.id)
        
        if len(args) < 2:
            await message.answer("請輸入正確格式：`/remove [站點名稱 或 ID]` 或 `/remove all`", parse_mode="Markdown")
            return
            
        target = args[1].lower()
        if target == "all":
            self.user_service.clear_all_subscriptions(user_id)
            await message.answer("✅ 已成功清空你所有的監控任務。")
            return

        matches = await self._find_stations(target)
        if not matches:
            await message.answer(f"❓ 找不到任何站點符合『{target}』。")
            return
            
        if len(matches) > 1:
            self._last_search_results[user_id] = {
                "matches": matches,
                "command": "remove",
                "args": []
            }
            resp = "🧐 *找到多個可能要移除的站點，請輸入編號來確認：*\n\n"
            for i, s in enumerate(matches, 1):
                resp += f"{i}. 🏠 `{s.sna}` (ID: `{s.sno}`)\n"
            await message.answer(resp, parse_mode="Markdown")
            return
            
        # One match
        selected = matches[0]
        self.user_service.remove_subscription(user_id, selected.sno)
        await message.answer(f"✅ 已成功移除站點 `[{selected.sna}]` 的監控任務。", parse_mode="Markdown")


    async def cancel_handler(self, message: Message):
        if str(message.chat.id) in self._last_search_results:
            del self._last_search_results[str(message.chat.id)]
        await message.answer("已取消當前選擇操作。")

    async def location_handler(self, message: Message):
        lat = message.location.latitude
        lng = message.location.longitude
        
        stations = await self._get_station_cache()
        
        # Calculate distances
        scored_stations = []
        for s in stations:
            dist = calculate_distance(lat, lng, s.lat, s.lng)
            scored_stations.append((dist, s))
            
        # Sort by distance
        scored_stations.sort(key=lambda x: x[0])
        
        top_5 = scored_stations[:5]
        text = "📍 *離你最近的 5 個站點：*\n\n"
        for dist, s in top_5:
            d_m = dist * 1000 # to meters
            text += f"🏠 `{s.sna}`\n   ID: `{s.sno}` | 距離: {d_m:.0f}m\n\n"
            
        text += "💡 點擊 ID 即可複製，並使用 `/add [ID] [門檻]` 開啟監控。"
        await message.answer(text, parse_mode="Markdown")

    async def text_handler(self, message: Message):
        text = message.text
        
        # 1. Direct Name/ID search (if not command)
        if len(text) >= 2 and not text.startswith("/"):
            matches = await self._find_stations(text)
            
            if matches:
                matches = matches[:8] # Limit results
                resp = f"🔎 *找到相關站點 ({len(matches)} 筆)：*\n\n"
                for s in matches:
                    resp += f"🏠 `{s.sna}`\n   ID: `{s.sno}` | 區域: {s.sarea or '無'}\n\n"
                resp += "💡 找到後，使用 `/add [名稱] [門檻]` 或 `/query [名稱]`。"
                await message.answer(resp, parse_mode="Markdown")
                return

        # 2. NLP Attempt (Existing)
        rrule = parse_natural_language_to_rrule(text)
        station_match = re.search(r'\d{9}', text)
        station_id = station_match.group(0) if station_match else None
        
        # Detect bike type
        bike_type = "any"
        if "電輔" in text or "電" in text:
            bike_type = "electric"
        elif "普通" in text or "一般" in text:
            bike_type = "normal"
        
        if rrule and station_id:
            stations = await self._get_station_cache()
            sna = next((s.sna for s in stations if s.sno == station_id), station_id)
            
            await self.user_service.register_subscription(
                user_id=str(message.chat.id),
                station_id=station_id,
                threshold=3, 
                rrule=rrule,
                bike_type=bike_type
            )
            type_label = {"any": "兩者", "normal": "普通", "electric": "電輔"}[bike_type]
            await message.answer(
                f"🤖 *我聽懂了！*\n"
                f"已為你設定：\n"
                f"📍 站點：`{sna}`\n"
                f"🚲 車型：{type_label}\n"
                f"📅 循環：`{rrule}`\n"
                f"門檻預設為 3 輛。你可以隨時用 /list 查看。",
                parse_mode="Markdown"
            )
        else:
            await message.answer("抱歉，我還沒聽懂這個指令。\n💡 傳送『座標』給我直接尋找最近站點，或輸入『站點關鍵字』搜尋。")

    async def set_commands(self):
        commands = [
            types.BotCommand(command="start", description="開始使用 BikeGuard"),
            types.BotCommand(command="add", description="新增訂閱 (可使用站點名/ID)"),
            types.BotCommand(command="list", description="列出目前所有訂閱 (顯示名稱)"),
            types.BotCommand(command="remove", description="移除訂閱 (可使用站點名/ID)"),
            types.BotCommand(command="query", description="查詢站點詳情 (含即時資料)"),
            types.BotCommand(command="cancel", description="取消目前操作")
        ]
        await self.bot.set_my_commands(commands)



    async def start(self):
        logging.info("Starting Telegram Bot...")
        await self.set_commands()
        await self.dp.start_polling(self.bot)
