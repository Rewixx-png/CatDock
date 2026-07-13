import logging
from aiogram import F, Router, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest

from config import SERVERS
from utils.filters import IsAdmin
from states.user_states import TerminalState
from keyboards.admin import get_terminal_exit_keyboard
from lexicon import LEXICON
from utils.ssh_runner import run_command_on_server
import asyncssh 
from roles import UserRole

router = Router()
router.message.filter(IsAdmin(min_level=UserRole.CO_OWNER))
router.callback_query.filter(IsAdmin(min_level=UserRole.CO_OWNER))

@router.callback_query(F.data == "terminal_menu")
async def terminal_server_selection(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    for server_id, server_info in SERVERS.items():
        builder.row(types.InlineKeyboardButton(
            text=f"🔌 {server_info['name']}",
            callback_data=f"select_terminal_server:{server_id}"
        ))
    builder.row(types.InlineKeyboardButton(
        text=LEXICON.get('ru', {}).get('back_to_admin_panel_button'),
        callback_data="admin_panel"
    ))
    await callback.message.edit_caption(
        caption="Выберите сервер для подключения терминала:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@router.callback_query(F.data.startswith("select_terminal_server:"))
async def start_terminal_session(callback: types.CallbackQuery, state: FSMContext):
    server_id = callback.data.split(":")[1]
    server_name = SERVERS[server_id]['name']

    await state.set_state(TerminalState.waiting_for_command)
    await state.update_data(server_id=server_id)

    await callback.message.delete()
    await callback.message.answer(
        f"Вы вошли в режим терминала для сервера <b>{server_name}</b>.\n"
        "Отправьте команду для выполнения. Для выхода нажмите кнопку ниже.",
        reply_markup=get_terminal_exit_keyboard()
    )
    await callback.answer()

@router.message(TerminalState.waiting_for_command)
async def execute_terminal_command(message: types.Message, state: FSMContext, bot: Bot):
    command = message.text
    data = await state.get_data()
    server_id = data['server_id']
    server_name = SERVERS[server_id]['name']
    last_output_message_id = data.get('last_output_message_id')

    try:
        await message.delete()
    except TelegramBadRequest:
        pass

    output_text = (
        f"🖥️ <b>Терминал: {server_name}</b>\n"
        f"<b>></b> <code>{command}</code>\n\n"
    )

    try:
        result = await run_command_on_server(server_id, command, check=False, timeout=60)

        if result.stdout:
            output_text += f"<b>Вывод:</b>\n<pre>{result.stdout.strip()}</pre>"
        if result.stderr:
            output_text += f"\n<b>Ошибка выполнения (stderr):</b>\n<pre>{result.stderr.strip()}</pre>"
        if not result.stdout and not result.stderr:
            output_text += "<b>Команда не вернула вывод.</b>"

    except (TimeoutError, asyncssh.process.TimeoutError):
        output_text += "❌ <b>ОШИБКА:</b> Команда выполнялась слишком долго (более 60 секунд) и была прервана."
    except Exception as e:
        output_text += f"❌ <b>КРИТИЧЕСКАЯ ОШИБКА ВЫПОЛНЕНИЯ:</b>\n<pre>{e}</pre>"

    try:
        if last_output_message_id:
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=last_output_message_id,
                text=output_text,
                reply_markup=get_terminal_exit_keyboard()
            )
        else:
            sent_message = await bot.send_message(message.chat.id, output_text, reply_markup=get_terminal_exit_keyboard())
            await state.update_data(last_output_message_id=sent_message.message_id)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            pass
        elif "message is too long" in str(e):
            await bot.send_message(message.chat.id, output_text[:4090] + "...`</pre>\n\n<b>(сообщение обрезано)</b>", reply_markup=get_terminal_exit_keyboard())
        else:
            sent_message = await bot.send_message(message.chat.id, output_text, reply_markup=get_terminal_exit_keyboard())
            await state.update_data(last_output_message_id=sent_message.message_id)

@router.callback_query(F.data == "cancel_terminal")
async def exit_terminal_session(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Сессия терминала завершена.")
    await callback.answer("Вы вышли из режима терминала.")
