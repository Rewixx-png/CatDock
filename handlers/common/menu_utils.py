from aiogram import types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
import logging
import asyncio

import database as db
from config import SERVERS, IMAGES, TARIFFS, DEFAULT_CPU_LIMIT
from keyboards import get_container_management_keyboard, get_orphaned_container_management_keyboard
from states.user_states import UserBotManageState
import utils.docker as dm
from lexicon import LEXICON
from roles import UserRole

def format_seconds_to_dhms(seconds):
    if not isinstance(seconds, (int, float)) or seconds <= 0: return "Время истекло"
    if seconds > 99999999:
        return "Навсегда 👑"
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    return f"{int(days)} д. {int(hours)} ч. {int(minutes)} м."

async def set_loading_state(callback: types.CallbackQuery, menu_name: str):
    try:
        user_id = callback.from_user.id
        language_code = await db.get_user_language(user_id) or 'ru'
        lex = LEXICON.get(language_code, LEXICON['ru'])

        loading_text = lex.get('loading_state_text', "⏳ Loading: {menu_name}...").format(menu_name=menu_name)

        if callback.message.caption is not None:
            await callback.message.edit_caption(caption=loading_text, reply_markup=None)
        else:
            await callback.message.edit_text(text=loading_text, reply_markup=None)

    except TelegramBadRequest as e:
        if "message is not modified" not in str(e) and "message to edit not found" not in str(e):
             logging.warning(f"Failed to set loading state: {e}")
    except Exception as e:
        logging.warning(f"Failed to set loading state: {e}")

async def _update_management_menu_with_stats(
    bot: Bot, message: types.Message, container_id: int, is_admin_view: bool, 
    admin_back_callback: str | None, from_page: int, actor_user_id: int
):
    user_id = message.chat.id
    language_code = await db.get_user_language(user_id) or 'ru'
    lex = LEXICON[language_code]
    container = await db.get_container_for_actor(container_id, actor_user_id)

    if not container:
        return

    try:
        status = await asyncio.wait_for(dm.get_container_status(container['server_id'], container['container_name']), timeout=10.0)
    except (asyncio.TimeoutError, Exception):
        status = 'error'

    is_frozen = bool(container.get('is_frozen', 0))

    try:
        stats = await asyncio.wait_for(dm.get_container_stats(container['server_id'], container['container_name']), timeout=10.0)
    except (asyncio.TimeoutError, Exception):
        stats = None

    try:
        session_status_key = await asyncio.wait_for(dm.get_session_status(container['server_id'], container['container_name'], container['image_id']), timeout=10.0)
    except (asyncio.TimeoutError, Exception):
        session_status_key = 'error'

    if is_frozen:
        status_text = lex.get('status_frozen', 'status_frozen')
    else:
        status_text = {
            'running': lex.get('status_running', 'status_running'), 'stopped': lex.get('status_exited', 'status_exited'), 'exited': lex.get('status_exited', 'status_exited'),
            'restarting': lex.get('status_restarting', 'status_restarting'), 'not_found': lex.get('status_not_found', 'status_not_found'), 'error': lex.get('status_error', 'status_error')
        }.get(status, f"⚙️ {status.capitalize()}")

    stats_text = ""
    if status == 'running' and stats:
        cpu_limit_cores = container.get('cpu_limit') or DEFAULT_CPU_LIMIT
        cpu_limit_percent = cpu_limit_cores * 100
        cpu_usage_percent = stats.get('cpu_usage', 0.0)

        cpu_status_message = lex.get('cpu_status_high') if cpu_usage_percent > (cpu_limit_percent / 2) else lex.get('cpu_status_normal')

        cpu_stats = lex.get('cpu_stats_format', "CPU: {usage:.2f}% / {limit:.2f}% | {status}").format(
            usage=cpu_usage_percent,
            limit=cpu_limit_percent,
            status=cpu_status_message
        )
        ram_stats = f"RAM: {stats.get('ram_raw', 'Н/Д')}"

        stats_text = lex.get('container_stats_text').format(
            cpu_stats=cpu_stats,
            ram_stats=ram_stats
        )

    not_found_explanation = ""
    if status == 'not_found':
        not_found_explanation = lex.get('not_found_explanation', "")

    session_status_text = lex.get(f"session_status_{session_status_key}", 'Н/Д')

    server_info = SERVERS.get(container['server_id'])
    server_name = server_info.get('name', container['server_id']) if server_info else container['server_id']
    image = IMAGES.get(container['image_id'], {})
    is_pending_transfer = bool(await db.get_active_token_for_container(container_id))

    actual_ram_mb = container.get('ram_mb') or TARIFFS.get(container['tariff_id'], {}).get('ram_mb', 'N/A')

    text = lex.get('manage_userbot_info', 'manage_userbot_info').format(
        container_id=container_id,
        container_name=container['container_name'],
        server_name=server_name,
        tariff_name=TARIFFS.get(container['tariff_id'], {}).get('name', 'N/A'),
        actual_ram_mb=actual_ram_mb,
        image_name=image.get('name', 'N/A'),
        status_text=status_text,
        transfer_status=lex.get('transfer_status_pending') if is_pending_transfer else lex.get('transfer_status_active'),
        remaining_time=format_seconds_to_dhms(container.get('remaining_seconds')),
        session_status_text=session_status_text
    ) + stats_text + not_found_explanation

    markup = await get_container_management_keyboard(container, status, language_code, is_admin_view, admin_back_callback, from_page=from_page)

    try:
        await bot.edit_message_text(
            text=text,
            chat_id=message.chat.id,
            message_id=message.message_id,
            reply_markup=markup
        )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            return
        logging.warning(f"Не удалось обновить меню статистики: {e}")

async def show_management_menu(
    event: types.CallbackQuery | types.Message,
    container_id: int,
    state: FSMContext,
    bot: Bot,
    is_admin_view: bool = False,
    admin_back_callback: str | None = None,
    from_page: int = 0
) -> bool:
    if isinstance(event, types.CallbackQuery):
        message = event.message
        user_id = event.from_user.id
    else:
        message = event
        user_id = event.from_user.id

    language_code = await db.get_user_language(user_id) or 'ru'
    lex = LEXICON[language_code]
    container = await db.get_container_for_actor(container_id, user_id)

    if not container:
        if isinstance(event, types.CallbackQuery):
            await event.answer("❌ UserBot не найден или недоступен.", show_alert=True)
        return False

    user_role = await db.get_user_role(user_id)
    is_admin_view = bool(
        user_id != container['user_id'] and user_role >= UserRole.ADMIN
    )

    await state.set_state(UserBotManageState.managing)
    await state.update_data(container_id=container_id)

    server_info = SERVERS.get(container['server_id'])
    is_orphaned = server_info is None

    if is_orphaned:
        text = lex.get('orphaned_container_warning').format(server_name=container['server_id'])
        markup = get_orphaned_container_management_keyboard(container, language_code, is_admin_view, admin_back_callback, from_page)
        try:
             await message.edit_text(text=text, reply_markup=markup)
        except TelegramBadRequest:
             await message.answer(text, reply_markup=markup)
        return True

    loading_text = lex.get('status_loading', "(Загружаем...)")
    server_name = server_info.get('name', container['server_id'])
    image = IMAGES.get(container['image_id'], {})
    is_pending_transfer = bool(await db.get_active_token_for_container(container_id))

    actual_ram_mb = container.get('ram_mb') or TARIFFS.get(container['tariff_id'], {}).get('ram_mb', 'N/A')

    initial_text = lex.get('manage_userbot_info', 'manage_userbot_info').format(
        container_id=container_id,
        container_name=container['container_name'],
        server_name=server_name,
        tariff_name=TARIFFS.get(container['tariff_id'], {}).get('name', 'N/A'),
        actual_ram_mb=actual_ram_mb,
        image_name=image.get('name', 'N/A'),
        status_text=loading_text,
        transfer_status=lex.get('transfer_status_pending') if is_pending_transfer else lex.get('transfer_status_active'),
        remaining_time=format_seconds_to_dhms(container.get('remaining_seconds')),
        session_status_text=loading_text
    )

    initial_markup = await get_container_management_keyboard(container, 'loading', language_code, is_admin_view, admin_back_callback, from_page=from_page)

    try:
        if isinstance(event, types.CallbackQuery):
            await message.edit_text(text=initial_text, reply_markup=initial_markup)
        else:
            await message.answer(text=initial_text, reply_markup=initial_markup)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            try:
                await message.delete()
            except TelegramBadRequest:
                pass
            sent_msg = await bot.send_message(chat_id=user_id, text=initial_text, reply_markup=initial_markup)
            message = sent_msg

    asyncio.create_task(_update_management_menu_with_stats(
        bot, message, container_id, is_admin_view, admin_back_callback, from_page,
        user_id,
    ))

    return True
