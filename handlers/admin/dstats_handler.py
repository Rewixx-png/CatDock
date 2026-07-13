import logging
import asyncio
import json
from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import BufferedInputFile, InputMediaPhoto

from config import SERVERS
from utils.filters import IsAdmin
from roles import UserRole
from keyboards.admin import get_dstats_server_keyboard, get_dstats_refresh_keyboard
from utils.ssh_runner import run_command_on_server
from utils.dstats_graph import generate_dstats_image

router = Router()
router.message.filter(IsAdmin(min_level=UserRole.ADMIN))
router.callback_query.filter(IsAdmin(min_level=UserRole.ADMIN))

@router.message(Command("dstats"))
async def cmd_dstats_start(message: types.Message):
    await message.answer(
        "🐳 <b>Docker Live Stats</b>\n\nВыберите сервер для анализа контейнеров:",
        reply_markup=get_dstats_server_keyboard()
    )

@router.callback_query(F.data == "admin_dstats_menu")
async def back_to_dstats_menu(callback: types.CallbackQuery):
    try: await callback.message.delete()
    except: pass
    await callback.message.answer(
        "🐳 <b>Docker Live Stats</b>\n\nВыберите сервер для анализа контейнеров:",
        reply_markup=get_dstats_server_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data.startswith("dstats_select:"))
@router.callback_query(F.data.startswith("dstats_refresh:"))
async def dstats_process(callback: types.CallbackQuery, bot: Bot):
    action = callback.data.split(":")[0]
    server_id = callback.data.split(":")[1]
    server_name = SERVERS.get(server_id, {}).get('name', server_id)

    if "refresh" not in action:
        try:
            await callback.message.edit_text(f"⏳ <b>{server_name}:</b> Сбор метрик Docker...")
        except TelegramBadRequest: pass
    else:
        await callback.answer("🔄 Обновление...", show_alert=False)

    remote_cmd = "docker stats --no-stream --format '{{.Name}}|;|{{.CPUPerc}}|;|{{.MemUsage}}|;|{{.MemPerc}}|;|{{.NetIO}}|;|{{.BlockIO}}|;|{{.PIDs}}'"

    try:
        result = await run_command_on_server(server_id, remote_cmd, timeout=20)
        
        if result.exit_status != 0:
            raise Exception(f"Docker Error: {result.stderr}")

        stats_list = []
        raw_lines = result.stdout.strip().splitlines()
        
        for line in raw_lines:
            parts = line.split('|;|')
            if len(parts) < 7: continue
            
            stats_list.append({
                'Name': parts[0],
                'CPUPerc': parts[1],
                'MemUsage': parts[2],
                'MemPerc': parts[3],
                'NetIO': parts[4],
                'BlockIO': parts[5],
                'PIDs': parts[6]
            })

        def parse_cpu(x):
            try: return float(x['CPUPerc'].replace('%', ''))
            except: return 0.0
            
        stats_list.sort(key=parse_cpu, reverse=True)

        if not stats_list:
            raise Exception("Нет активных контейнеров")

        image_bytes = await asyncio.to_thread(generate_dstats_image, stats_list, server_name)
        photo_file = BufferedInputFile(image_bytes.read(), filename=f"dstats_{server_id}.png")
        
        markup = get_dstats_refresh_keyboard(server_id)

        if "refresh" in action and callback.message.photo:
            media = InputMediaPhoto(media=photo_file, caption=f"🐳 <b>Docker Stats: {server_name}</b>")
            await callback.message.edit_media(media, reply_markup=markup)
        else:
            try: await callback.message.delete()
            except: pass

            await bot.send_photo(
                chat_id=callback.message.chat.id,
                message_thread_id=callback.message.message_thread_id,
                photo=photo_file,
                caption=f"🐳 <b>Docker Stats: {server_name}</b>",
                reply_markup=markup
            )

    except Exception as e:
        logging.error(f"DSTATS Fail on {server_id}: {e}")
        error_msg = f"❌ Ошибка сбора данных с {server_name}:\n<code>{e}</code>"
        try:
            if callback.message.photo:
                await callback.message.edit_caption(caption=error_msg, reply_markup=get_dstats_refresh_keyboard(server_id))
            else:
                await callback.message.edit_text(error_msg, reply_markup=get_dstats_server_keyboard())
        except: pass
