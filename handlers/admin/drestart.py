import logging
import asyncio
from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest

import database as db
from config import SERVERS, DEFAULT_CPU_LIMIT
from utils.filters import IsAdmin
from roles import UserRole
from keyboards.admin import get_drestart_server_keyboard
import utils.docker as dm
from utils.action_logger import log_action

router = Router()
router.message.filter(IsAdmin(min_level=UserRole.CO_OWNER))
router.callback_query.filter(IsAdmin(min_level=UserRole.CO_OWNER))

ANOMALY_PID_THRESHOLD = 5000

@router.message(Command("drestart"))
async def cmd_drestart(message: types.Message):
    await message.answer(
        "🐌 <b>Плавная перезагрузка (Smooth Restart)</b>\n\n"
        "Эта команда:\n"
        "1. Проверит аномалии (PIDs > 5000).\n"
        "2. Остановит ВСЕ контейнеры на сервере.\n"
        "3. Будет запускать их по одному с бустом CPU и задержкой 20 сек.\n\n"
        "⚠️ <b>Процесс займет много времени!</b>\n"
        "Выберите сервер:",
        reply_markup=get_drestart_server_keyboard()
    )

@router.callback_query(F.data.startswith("drestart_select:"))
async def process_drestart(callback: types.CallbackQuery, bot: Bot):
    server_id = callback.data.split(":")[1]
    server_name = SERVERS.get(server_id, {}).get('name', server_id)

    try:
        await callback.message.edit_text(f"⏳ <b>{server_name}:</b> Анализ процессов...")
    except TelegramBadRequest: pass

    try:
        pids_map = await dm.get_all_containers_pids(server_id)
        anomaly_text = ""

        for name, pids in pids_map.items():
            if not name.startswith("cat-"): continue

            if pids > ANOMALY_PID_THRESHOLD:
                anomaly_text += f"⚠️ <b>Аномалия:</b> {name} ({pids} процессов)\n"

                container = await db.get_container_by_name(name)
                if container:
                    try:
                        await bot.send_message(
                            container['user_id'],
                            f"⚠️ <b>Внимание!</b>\n"
                            f"Ваш контейнер <b>{name}</b> потребляет аномальное количество ресурсов ({pids} процессов).\n"
                            f"Он будет принудительно перезагружен. Пожалуйста, проверьте скрипты на наличие бесконечных циклов."
                        )
                    except Exception:
                        pass

        if anomaly_text:
            await callback.message.edit_text(f"{anomaly_text}\n⏳ Останавливаю контейнеры...")
        else:
            await callback.message.edit_text("✅ Аномалий нет.\n⏳ Останавливаю контейнеры...")

    except Exception as e:
        logging.error(f"Drestart PID check failed: {e}")

    containers = await dm.stop_all_rew_containers(server_id)

    if not containers:
        await callback.message.edit_text("❌ На сервере нет активных контейнеров 'cat-'.")
        return

    log_message = f"Останавливаю контейнеры... ✅\n"
    log_message += f"Всего в очереди: <b>{len(containers)}</b>\n\n"

    await callback.message.edit_text(log_message)

    total = len(containers)

    for i, container_name in enumerate(containers, 1):
        try:
            
            container_db = await db.get_container_by_name(container_name)
            cpu_limit = container_db.get('cpu_limit', DEFAULT_CPU_LIMIT) if container_db else DEFAULT_CPU_LIMIT

            await dm.run_command_on_server(server_id, f"docker update --cpus=\"2.0\" {container_name}", check=False)

            await dm.start_container(server_id, container_name)

            await asyncio.sleep(20)

            await dm.run_command_on_server(server_id, f"docker update --cpus=\"{cpu_limit}\" {container_name}", check=False)

            line = f"Запускаю контейнер {container_name} ✅ [{i}/{total}]\n"
            log_message += line

            if len(log_message) > 3500:
                lines = log_message.split('\n')
                header = lines[:2]
                last_lines = lines[-15:]
                display_text = "\n".join(header) + "\n... (скрыто) ...\n" + "\n".join(last_lines)
            else:
                display_text = log_message

            try:
                await callback.message.edit_text(display_text, parse_mode="HTML")
            except TelegramBadRequest: pass

        except Exception as e:
            logging.error(f"Error restart {container_name}: {e}")
            log_message += f"❌ Ошибка {container_name}: {e}\n"
            try: await callback.message.edit_text(log_message)
            except: pass

    await log_action(bot, callback.from_user, f"выполнил плавную перезагрузку ({total} шт) на {server_name}")
    final_text = log_message + "\n🏁 <b>Плавная перезагрузка завершена!</b>"

    if len(final_text) > 4000:
        await callback.message.delete()
        await callback.message.answer("🏁 <b>Плавная перезагрузка завершена!</b>\n(Лог был слишком длинным)")
    else:
        await callback.message.edit_text(final_text)
