import asyncio
import logging
import os
import re
import json # Added import json
from datetime import datetime
from typing import List, Optional, Dict, Any, Union # Added Any, Union for more precise typing
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message

from typing import List, Dict, Optional
from src.core.user_service import UserService
from src.core.station_service import StationService
from src.utils.nlp_parser import parse_natural_language_to_rrule
from src.config.constants import DEFAULT_THRESHOLD
from src.utils.geo_utils import calculate_distance
from src.api.client import YouBikeClient
from src.models.schemas import StationInfo


class BikeGuardBot:

    def __init__(self, token: str, user_service: UserService, station_service: StationService, api_client: YouBikeClient):
        self.bot = Bot(token=token)
        self.dp = Dispatcher()
        self.user_service = user_service
        self.station_service = station_service
        self.api_client = api_client
        
        # Temp state for search disambiguation: user_id -> {"matches": [...], "command": "...", "args": [...]}
        self._last_search_results: Dict[str, dict] = {}
        
        self._setup_handlers()

    def _setup_handlers(self):
        self.dp.message.register(self.start_handler, Command("start", "help"))
        self.dp.message.register(self.add_handler, Command("add"))
        self.dp.message.register(self.list_handler, Command("list"))
        self.dp.message.register(self.remove_handler, Command("remove"))
        self.dp.message.register(self.query_handler, Command("query"))
        self.dp.message.register(self.cancel_handler, Command("cancel"))
        self.dp.message.register(self.number_selection_handler, lambda m: str(m.chat.id) in self._last_search_results)
        self.dp.message.register(self.location_handler, lambda m: m.location is not None)
        self.dp.message.register(self.text_handler) # Catch-all for NLP and search

    async def _get_station_cache(self) -> List[StationInfo]:
        """Transparently use StationService for all metadata needs."""
        return await self.station_service.get_stations()


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



    async def _check_and_cancel_pending(self, message: Message):
        """Internal helper to auto-cancel pending selections when a new command starts."""
        uid = str(message.chat.id)
        if uid in self._last_search_results:
            state = self._last_search_results.pop(uid)
            prev_cmd = state.get("command", "操作")
            await message.answer(f"⚠️ *偵測到新指令，已自動取消先前的 `{prev_cmd}` 操作環境。*", parse_mode="Markdown")

    async def start_handler(self, message: Message):
        await self._check_and_cancel_pending(message)
        chat_id = message.chat.id
        logging.info(f"Received /start or /help from user. Chat ID: {chat_id}")
        await message.answer(
            "🚲 *歡迎來到 BikeGuard YouBike 監控助手 v2.0* 🛡️\n\n"
            "我是你的 YouBike 守護者，能幫你監控熱門站點的剩餘車輛，讓你在出門前不再撲空！\n\n"
            "📍 *如何快速找點？*\n"
            "1️⃣ **傳送座標**：點擊附件傳送「位置」給我，我會列出最近的 5 個站點。\n"
            "2️⃣ **關鍵字搜尋**：直接傳送「名稱」（如：`科技大樓`）進行模糊匹配。\n\n"
            "⏰ *如何訂閱監控？*\n"
            "使用 `/add` 指令，格式如下：\n"
            "`/add [站點] [門檻] [頻率時間] [車型(可選)]`\n\n"
            "💡 *例如：*\n"
            "• `/add 科技大樓 3 每天 08:30` (2.0 普通)\n"
            "• `/add 中山國小 5 每天 17:30 電輔` (2.0E 電輔)\n\n"
            "🔍 *查詢即時資訊：*\n"
            "使用 `/query [名稱]` 查看即時車位、地址與詳細資料。\n\n"
            "📋 *其他指令：*\n"
            "/list - 查看目前的監控清單\n"
            "/remove [站點] - 移除監控任務\n"
            "/cancel - 取消目前的操作\n\n"
            "💡 *系統提示：* 我會在設定時間的 **20 分鐘前** 開始自動監控。",
            parse_mode="Markdown"
        )

    async def add_handler(self, message: Message):
        await self._check_and_cancel_pending(message)
        # Example: /add [名稱/ID] [門檻值] [時間規則] [車型]
        args = message.text.split()
        if len(args) < 2:
            await message.answer(
                "➕ *新增監控說明*\n格式：`/add [站點名稱 或 ID] [門檻值] [時間規則] [車型]`\n"
                "例如：`/add 科技大樓 3 每天 08:30`",
                parse_mode="Markdown"
            )
            return
        await self._process_add(message, args[1], args[2:])

    async def _process_add(self, message: Message, target_query: str, sub_args: List[str]):
        matches = await self._find_stations(target_query)
        
        if not matches:
            await message.answer(f"❓ 找不到任何站點符合『{target_query}』。請換個關鍵字試試。")
            return
            
        if len(matches) > 1:
            self._last_search_results[str(message.chat.id)] = {
                "matches": matches[:10],
                "command": "add",
                "args": sub_args
            }
            resp = "🧐 *找到多個相似站點，請輸入編號來選擇：*\n\n"
            for i, s in enumerate(matches[:10], 1):
                resp += f"{i}. 🏠 `{s.sna}` (ID: `{s.sno}`)\n"
            resp += "\n💡 *你也可以直接輸入新的名稱或 ID 重新搜尋。*"
            await message.answer(resp, parse_mode="Markdown")
            return
            
        # Exactly one match
        await self._register_sub_with_station(message, matches[0], sub_args)

    async def _register_sub_with_station(self, message: types.Message, station: StationInfo, sub_args: List[str]):
        # sub_args: [threshold, time_rule, bike_type...]
        try:
            threshold = int(sub_args[0]) if len(sub_args) > 0 else DEFAULT_THRESHOLD
        except (ValueError, IndexError):
            threshold = DEFAULT_THRESHOLD
            
        # 1. Extract bike type
        bike_type = "any"
        full_sub_text = " ".join(sub_args)
        if "電輔" in full_sub_text:
            bike_type = "electric"
        elif "普通" in full_sub_text or "一般" in full_sub_text:
            bike_type = "normal"
        
        type_display = {"any": "不限 (2.0/2.0E)", "normal": "一般 (2.0)", "electric": "電輔 (2.0E)"}[bike_type]

        # 2. Extract and parse time - Support one-time default
        if len(sub_args) <= 1:
            # Case 1: /add [station] [threshold?] -> 30m from now, once
            from datetime import timedelta
            target_time = datetime.now() + timedelta(minutes=30)
            rrule = f"ONCE:{target_time.isoformat()}"
            rule_display = f"單次提醒 (預設 30 分鐘後: {target_time.strftime('%H:%M')})"
        else:
            # Case 2: Natural language rrule
            full_text = " ".join(sub_args[1:])
            rrule = parse_natural_language_to_rrule(full_text)
            rule_display = f"規律提醒 (`{rrule}`)"

        await self.user_service.register_subscription(
            user_id=str(message.chat.id),
            station_id=station.sno,
            threshold=threshold,
            rrule=rrule,
            bike_type=bike_type
        )
        
        await message.answer(
            f"✅ *監控已開啟！*\n\n"
            f"📍 站點：`{station.sna}`\n"
            f"🎯 門檻：{threshold} 輛\n"
            f"🚲 車型：{type_display}\n"
            f"⏰ 規則：{rule_display}\n\n"
            f"💡 {'任務執行後會自動結束' if rrule == 'once' else '系統將自動持續監控'}。",
            parse_mode="Markdown"
        )

    async def number_selection_handler(self, message: Message):
        user_id = str(message.chat.id)
        if user_id not in self._last_search_results:
            return
            
        state = self._last_search_results[user_id]
        matches = state.get("matches", [])
        text = message.text or ""
        command = state.get("command")
        
        # 1. Handle Digit Selection
        if text.isdigit():
            try:
                choice_idx = int(text) - 1
                if 0 <= choice_idx < len(matches):
                    selected = matches[choice_idx]
                    
                    if command == "add":
                        await self._register_sub_with_station(message, selected, state.get("args", []))
                    elif command == "remove":
                        await self._check_and_process_remove_selection(message, selected)
                    elif command == "remove_slot":
                        # selected is actually a subscription dict here
                        self.user_service.remove_subscription_by_id(selected['id'])
                        await message.answer(f"✅ 已成功移除該時段的監控任務。", parse_mode="Markdown")
                    elif command == "query":
                        await self._send_detailed_query(message, selected)
                        
                    self._last_search_results.pop(user_id, None)
                    return
            except (ValueError, KeyError, TypeError):
                pass

        # 2. If NOT a digit: Treat as a RE-SEARCH for the existing command
        self._last_search_results.pop(user_id, None)
        
        if command == "add":
            await self._process_add(message, text, state.get("args", []))
        elif command == "query":
            await self._process_query(message, text)
        elif command == "remove":
            await self._process_remove(message, text)
        else:
            # Fallback to general text search if command unknown
            await self.text_handler(message)


    async def query_handler(self, message: Message):
        await self._check_and_cancel_pending(message)
        args = message.text.split()
        if len(args) < 2:
            await message.answer("🔍 請輸入 `/query [站點名稱 或 ID]` 來查詢詳細資訊。")
            return
        await self._process_query(message, args[1])

    async def _process_query(self, message: Message, target_query: str):
        matches = await self._find_stations(target_query)
        
        if not matches:
            await message.answer(f"❓ 找不到任何站點符合『{target_query}』。")
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
            resp += "\n💡 *你也可以直接輸入新的名稱或 ID 重新搜尋。*"
            await message.answer(resp, parse_mode="Markdown")
            return
            
        # Exactly one match
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
        await self._check_and_cancel_pending(message)
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

        await self._process_remove(message, target)

    async def _process_remove(self, message: Message, target_query: str):
        matches = await self._find_stations(target_query)
        if not matches:
            await message.answer(f"❓ 找不到任何站點符合『{target_query}』。")
            return
            
        if len(matches) > 1:
            self._last_search_results[str(message.chat.id)] = {
                "matches": matches[:10],
                "command": "remove",
                "args": []
            }
            resp = "🧐 *找到多個可能要移除的站點，請輸入編號來確認：*\n\n"
            for i, s in enumerate(matches[:10], 1):
                resp += f"{i}. 🏠 `{s.sna}` (ID: `{s.sno}`)\n"
            resp += "\n💡 *你也可以直接輸入新的名稱或 ID 重新搜尋。*"
            await message.answer(resp, parse_mode="Markdown")
            return
            
        # One station match
        selected_station = matches[0]
        await self._check_and_process_remove_selection(message, selected_station)

    async def _check_and_process_remove_selection(self, message: Message, station: StationInfo):
        user_id = str(message.chat.id)
        subs = self.user_service.get_user_station_subscriptions(user_id, station.sno)
        
        if not subs:
            await message.answer(f"❓ 你目前沒有訂閱 `[{station.sna}]` 的監控任務。")
            return

        if len(subs) > 1:
            self._last_search_results[user_id] = {
                "matches": subs,
                "command": "remove_slot",
                "args": []
            }
            resp = f"🧐 *站點 `[{station.sna}]` 有多個監控時段，請輸入編號來選擇要刪除哪一個：*\n\n"
            for i, s in enumerate(subs, 1):
                resp += f"{i}. ⏰ 規則：`{s['rrule']}` | 門檻：{s['threshold']}\n"
            resp += "\n⚠️ *注意：此處只能輸入數字編號選擇。*"
            await message.answer(resp, parse_mode="Markdown")
            return
            
        # Only one subscription
        self.user_service.remove_subscription_by_id(subs[0]['id'])
        await message.answer(f"✅ 已成功移除站點 `[{station.sna}]` 的監控任務 (`{subs[0]['rrule']}`)。", parse_mode="Markdown")


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
            await message.answer(
                "❌ *抱歉，我還沒聽懂這個指令。*\n\n"
                "💡 **你可以試試看：**\n"
                "• 傳送「站點名稱」直接搜尋站點。\n"
                "• 傳送「地理座標」尋找附近站點。\n"
                "• 使用 `/add 站點名 門檻 時間` 設定監控。\n"
                "• 輸入 `/help` 查看完整教學。",
                parse_mode="Markdown"
            )

    async def set_commands(self):
        commands = [
            types.BotCommand(command="start", description="開始使用 BikeGuard"),
            types.BotCommand(command="help", description="查看詳細功能教學"),
            types.BotCommand(command="add", description="新增監控 (站點名/時間)"),
            types.BotCommand(command="list", description="列出目前訂閱項目"),
            types.BotCommand(command="remove", description="移除監控項目"),
            types.BotCommand(command="query", description="查詢站點即時資訊"),
            types.BotCommand(command="cancel", description="取消目前操作")
        ]
        await self.bot.set_my_commands(commands)



    async def start(self):
        logging.info("Starting Telegram Bot...")
        await self.set_commands()
        await self.dp.start_polling(self.bot)
