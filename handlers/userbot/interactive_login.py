import asyncio
import logging
import re
from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
import asyncssh

import database as db
from states.user_states import InteractiveLoginState
from keyboards import get_cancel_keyboard
from utils.ssh_runner import create_interactive_process
from config import IMAGES

router = Router()

active_sessions = {}

SESSION_TIMEOUT = 1800

ANSI_CLEANER = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

async def session_timeout_timer(user_id: int, bot: Bot, state: FSMContext):
    try:
        await asyncio.sleep(SESSION_TIMEOUT)

        if user_id in active_sessions:
            logging.info(f"Интерактивная сессия для {user_id} завершена по тайм-ауту ({SESSION_TIMEOUT}с).")

            session_data = active_sessions[user_id]
            process = session_data.get('process')

            if process and process.returncode is None:
                process.terminate()

            read_task = session_data.get('read_task')
            if read_task and not read_task.done():
                read_task.cancel()

            del active_sessions[user_id]

            await state.clear()

            try:
                await bot.send_message(
                    user_id, 
                    "⏳ <b>Время настройки истекло.</b>\n\n"
                    "Меню интерактивного входа было закрыто из-за бездействия.\n"
                    "⚠️ <b>Это НЕ влияет на работу вашего UserBot'а, если он уже запущен.</b>\n\n"
                    "Если вы не успели ввести код, просто начните процедуру входа заново в меню управления."
                )
            except Exception as e:
                logging.warning(f"Не удалось отправить уведомление о тайм-ауте пользователю {user_id}: {e}")

    except asyncio.CancelledError:
        pass

async def read_from_process(user_id: int, bot: Bot, process: asyncssh.SSHClientProcess, state: FSMContext):
    try:
        while not process.stdout.at_eof():
            output_buffer = b''

            while True:
                try:
                    chunk = await asyncio.wait_for(process.stdout.read(4096), timeout=0.5)
                    if not chunk:
                        break

                    if isinstance(chunk, str):
                        output_buffer += chunk.encode('utf-8', errors='ignore')
                    else:
                        output_buffer += chunk

                except asyncio.TimeoutError:
                    break

            if output_buffer:
                decoded_text = output_buffer.decode('utf-8', errors='ignore')
                cleaned_text = ANSI_CLEANER.sub('', decoded_text).strip()

                if cleaned_text:
                    try:
                        CHUNK_SIZE = 4000 

                        if "Please enter the code you received:" in cleaned_text:
                            await bot.send_message(user_id, f"<pre>{cleaned_text}</pre>")
                            await bot.send_message(user_id, "<i>(Подсказка: отправьте код в формате с тире, например: 71-286. Тире будет удалено автоматически.)</i>")
                        else:
                            if len(cleaned_text) > CHUNK_SIZE:
                                for i in range(0, len(cleaned_text), CHUNK_SIZE):
                                    chunk_text = cleaned_text[i:i + CHUNK_SIZE]
                                    await bot.send_message(user_id, f"<pre>{chunk_text}</pre>")
                            else:
                                await bot.send_message(user_id, f"<pre>{cleaned_text}</pre>")

                    except TelegramBadRequest as e:
                        logging.warning(f"Не удалось отправить блок вывода пользователю {user_id}: {e}")

            if process.stdout.at_eof():
                break

        exit_status = await process.wait()
        logging.info(f"Интерактивная сессия для {user_id} завершилась с кодом {exit_status}.")
        await bot.send_message(user_id, f"✅ Сессия завершена (код выхода: {exit_status}).")

    except asyncio.CancelledError:
        await bot.send_message(user_id, "✅ Сессия принудительно завершена.")
    except Exception as e:
        logging.error(f"Критическая ошибка в задаче чтения для {user_id}: {e}", exc_info=True)
        await bot.send_message(user_id, "❌ Произошла критическая ошибка в сессии. Она будет завершена.")
    finally:
        if user_id in active_sessions:
            timeout_task = active_sessions[user_id].get('timeout_task')
            if timeout_task and not timeout_task.done():
                timeout_task.cancel()
            del active_sessions[user_id]

        await state.clear()

@router.callback_query(F.data.startswith("interactive_login:"))
async def start_interactive_login(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    user_id = callback.from_user.id
    if user_id in active_sessions:
        await callback.answer("У вас уже есть активная сессия. Сначала завершите ее или подождите.", show_alert=True)
        return

    container_id = int(callback.data.split(":")[1])
    container = await db.get_container_by_id(container_id)

    if not container:
        await callback.answer("❌ Контейнер не найден.", show_alert=True)
        return

    module_name = 'heroku'
    if container['image_id'] == 'legacy':
        module_name = 'legacy' 

    command_str = f"docker exec -i {container['container_name']} python3 -m {module_name} --root --no-web"

    try:
        await callback.message.delete()
    except TelegramBadRequest as e:
        logging.warning(f"Не удалось удалить сообщение при запуске сессии (возможно, в чате): {e}")

    await callback.answer("⏳ Запускаем интерактивную сессию...")

    try:
        process = await create_interactive_process(container['server_id'], command_str)

        if not process:
            raise Exception("Не удалось создать интерактивный процесс на сервере.")

        await state.set_state(InteractiveLoginState.in_session)

        read_task = asyncio.create_task(read_from_process(user_id, bot, process, state))

        timeout_task = asyncio.create_task(session_timeout_timer(user_id, bot, state))

        active_sessions[user_id] = {
            'process': process,
            'read_task': read_task,
            'timeout_task': timeout_task
        }

        await bot.send_message(
            user_id,
            "🚀 <b>Интерактивный вход запущен!</b>\n\n"
            "1. Бот будет присылать сообщения из консоли.\n"
            "2. Отвечайте на сообщения бота, чтобы вводить данные (email, пароль, код).\n"
            "3. <b>Внимание:</b> Сессия автоматически закроется через 30 минут.\n\n"
            "Для принудительной отмены нажмите кнопку ниже.",
            reply_markup=get_cancel_keyboard("ru")
        )

    except Exception as e:
        await bot.send_message(user_id, f"❌ Ошибка запуска сессии: {e}")
        logging.error(f"Ошибка interactive_login для {user_id}: {e}", exc_info=True)
        await state.clear()

@router.message(InteractiveLoginState.in_session)
async def handle_user_input(message: types.Message):
    user_id = message.from_user.id
    if user_id not in active_sessions:
        await message.answer("Активная сессия не найдена. Пожалуйста, начните заново.")
        return

    session_data = active_sessions[user_id]
    process = session_data['process']
    read_task = session_data['read_task']

    if process.stdin.is_closing():
        await message.answer("Сессия уже завершается, ввод не принимается.")
        return

    try:
        user_input = message.text.replace('-', '').strip()
        input_data = user_input + '\n'

        process.stdin.write(input_data)
        await process.stdin.drain()

        try:
            await message.delete()
        except TelegramBadRequest:
            pass

    except (asyncssh.misc.ChannelOpenError, ConnectionResetError) as e:
        logging.warning(f"Канал для ввода (stdin) уже закрыт для {user_id}: {e}")
        await message.answer("Сессия завершена, ввод больше не принимается.")
        if not read_task.done():
            read_task.cancel()
    except Exception as e:
        logging.error(f"Ошибка записи в stdin для {user_id}: {e}", exc_info=True)
        await message.answer("Ошибка отправки данных. Сессия будет завершена.")
        if not read_task.done():
            read_task.cancel()

@router.callback_query(F.data == "cancel_payment", InteractiveLoginState.in_session)
async def cancel_interactive_login(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if user_id in active_sessions:
        session_data = active_sessions[user_id]
        process = session_data['process']
        read_task = session_data['read_task']
        timeout_task = session_data['timeout_task']

        if not read_task.done():
            read_task.cancel()

        if not timeout_task.done():
            timeout_task.cancel()

        if process.returncode is None:
            process.terminate()

        del active_sessions[user_id]

    await state.clear()
    try:
        await callback.message.delete()
    except TelegramBadRequest:
        pass
    await callback.message.answer("Интерактивная сессия отменена вручную.")
    await callback.answer("Сессия отменена.")
