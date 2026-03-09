import asyncio
import logging
import os
import re
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message

from src.core.user_service import UserService
from src.utils.nlp_parser import parse_natural_language_to_rrule
from src.config.constants import DEFAULT_THRESHOLD
from src.utils.geo_utils import calculate_distance
from src.api.client import YouBikeClient

class BikeGuardBot:

    def __init__(self, token: str, user_service: UserService, api_client: YouBikeClient):
        self.bot = Bot(token=token)
        self.dp = Dispatcher()
        self.user_service = user_service
        self.api_client = api_client
        self._setup_handlers()

    def _setup_handlers(self):
        self.dp.message.register(self.start_handler, Command("start"))
        self.dp.message.register(self.add_handler, Command("add"))
        self.dp.message.register(self.list_handler, Command("list"))
        self.dp.message.register(self.remove_handler, Command("remove"))
        self.dp.message.register(self.cancel_handler, Command("cancel"))
        self.dp.message.register(self.location_handler, lambda m: m.location is not None)
        self.dp.message.register(self.text_handler) # Catch-all for NLP and search

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
        # Example: /add 500101001 3 每天 08:30
        args = message.text.split()
        if len(args) < 3:
            await message.answer(
                "❌ *格式錯誤*\n請輸入：`/add [站點ID] [門檻值] [時間規則]`\n"
                "例如：`/add 500101001 3 每天 08:30` 或 `/add 500101001 3 每週五 17:00`",
                parse_mode="Markdown"
            )
            return
            
        station_id = args[1]
        try:
            threshold = int(args[2])
        except ValueError:
            await message.answer("❌ 門檻值必須是數字。")
            return
            
        # Parse the remaining text as the RRule
        nlp_text = " ".join(args[3:]) if len(args) > 3 else "每天 00:00"
        rrule = parse_natural_language_to_rrule(nlp_text)
        
        await self.user_service.register_subscription(
            user_id=str(message.chat.id),
            station_id=station_id,
            threshold=threshold,
            rrule=rrule
        )
        
        await message.answer(
            f"✅ *定時監控已開啟！*\n\n"
            f"📍 站點：`{station_id}`\n"
            f"🎯 門檻：{threshold} 輛\n"
            f"⏰ 規則：{nlp_text} (`{rrule}`)\n\n"
            f"機器人將在指定時間開始，若車輛低於門檻將持續提醒直到恢復或逾時。",
            parse_mode="Markdown"
        )


    async def list_handler(self, message: Message):
        subs = self.user_service.get_subscriptions(str(message.chat.id))
        if not subs:
            await message.answer("你目前沒有任何追蹤中的站點。")
            return
            
        text = "📋 *你的監控清單：*\n\n"
        for s in subs:
            text += f"📍 站點：`{s['station_id']}`\n   門檻：{s['threshold']} | 規則：`{s['rrule']}`\n\n"
        await message.answer(text, parse_mode="Markdown")

    async def remove_handler(self, message: Message):
        args = message.text.split()
        user_id = str(message.chat.id)
        
        if len(args) < 2:
            await message.answer("請輸入正確格式：`/remove [站點ID]` 或 `/remove all`", parse_mode="Markdown")
            return
            
        target = args[1].lower()
        if target == "all":
            self.user_service.clear_all_subscriptions(user_id)
            await message.answer("✅ 已成功清空你所有的監控任務。")
        else:
            self.user_service.remove_subscription(user_id, target)
            await message.answer(f"✅ 已成功移除站點 `{target}` 的監控任務。", parse_mode="Markdown")


    async def cancel_handler(self, message: Message):
        await message.answer("操作已取消。")

    async def location_handler(self, message: Message):
        lat = message.location.latitude
        lng = message.location.longitude
        
        stations = await self.api_client.fetch_station_list()
        
        # Calculate distances
        for s in stations:
            s.tot = calculate_distance(lat, lng, s.lat, s.lng) # Reusing 'tot' as temp distance storage
            
        # Sort by distance
        stations.sort(key=lambda x: x.tot)
        
        top_5 = stations[:5]
        text = "📍 *離你最近的 5 個站點：*\n\n"
        for s in top_5:
            dist = s.tot * 1000 # to meters
            text += f"🏠 `{s.sna}`\n   ID: `{s.sno}` | 距離: {dist:.0f}m\n   地址: {s.ar or '無'}\n\n"
            
        text += "💡 點擊 ID 即可複製，並使用 `/add [ID] [門檻]` 開啟監控。"
        await message.answer(text, parse_mode="Markdown")

    async def text_handler(self, message: Message):
        text = message.text
        
        # 1. Check if user is searching for a station name or location keyword
        if len(text) >= 2 and not text.startswith("/"):
            stations = await self.api_client.fetch_station_list()
            matches = [s for s in stations if text in s.sna or (s.ar and text in s.ar) or (s.sarea and text in s.sarea)]
            
            if matches:
                matches = matches[:8] # Limit results
                resp = f"🔎 *找到相關站點 ({len(matches)} 筆)：*\n\n"
                for s in matches:
                    resp += f"🏠 `{s.sna}`\n   ID: `{s.sno}` | 區域: {s.sarea or '無'}\n\n"
                resp += "💡 找到 ID 後，請使用 `/add [ID] [門檻]`。"
                await message.answer(resp, parse_mode="Markdown")
                return

        # 2. NLP Attempt (Existing)
        rrule = parse_natural_language_to_rrule(text)
        station_match = re.search(r'\d{9}', text)
        station_id = station_match.group(0) if station_match else None
        
        if rrule and station_id:
            await self.user_service.register_subscription(
                user_id=str(message.chat.id),
                station_id=station_id,
                threshold=3, 
                rrule=rrule
            )
            await message.answer(
                f"🤖 *我聽懂了！*\n"
                f"已為你設定：\n"
                f"📍 站點：`{station_id}`\n"
                f"📅 循環：`{rrule}`\n"
                f"門檻預設為 3 輛。你可以隨時用 /list 查看。",
                parse_mode="Markdown"
            )
        else:
            await message.answer("抱歉，我還沒聽懂這個指令。\n💡 傳送『座標』給我直接尋找最近站點，或輸入『站點關鍵字』搜尋。")

    async def set_commands(self):
        commands = [
            types.BotCommand(command="start", description="開始使用 BikeGuard"),
            types.BotCommand(command="add", description="新增訂閱 (例如: /add 500101001 3)"),
            types.BotCommand(command="list", description="列出目前所有訂閱"),
            types.BotCommand(command="remove", description="移除訂閱 (例如: /remove 1)"),
            types.BotCommand(command="cancel", description="取消目前操作")
        ]
        await self.bot.set_my_commands(commands)


    async def start(self):
        logging.info("Starting Telegram Bot...")
        await self.set_commands()
        await self.dp.start_polling(self.bot)
