import asyncio
import sqlite3
import logging
import os
import time
import random
import argparse
from dotenv import load_dotenv
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError, UserAdminInvalidError, ChatAdminRequiredError
from telethon.tl.types import ChannelParticipantsAdmins

KICK_BATCH_SIZE = 45
PAUSE_BETWEEN_BATCHES = 90
MIN_DELAY_BETWEEN_KICKS = 2.5
MAX_DELAY_BETWEEN_KICKS = 5.5

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv()

API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
SESSION_STRING = os.getenv("SESSION_STRING")
CHAT_ID = int(os.getenv("TARGET_CHAT_ID", -1002520056419))
DB_PATH = "rew_host.db"

async def main(dry_run: bool, delay: float):
    if not all([API_ID, API_HASH, SESSION_STRING, CHAT_ID]):
        logging.critical("ОШИБКА: Не все переменные окружения (.env) настроены! (API_ID, API_HASH, SESSION_STRING, TARGET_CHAT_ID)")
        return

    logging.info(f"Подключение к базе данных '{DB_PATH}'...")
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users")
        legit_users = {row[0] for row in cursor.fetchall()}
        conn.close()
        logging.info(f"Загружено {len(legit_users)} пользователей из базы данных.")
    except Exception as e:
        logging.critical(f"Не удалось подключиться к базе данных {DB_PATH}: {e}")
        return

    async with TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH) as client:
        logging.info("Подключение к Telegram...")
        me = await client.get_me()
        logging.info(f"Скрипт запущен от имени: {me.first_name} (@{me.username})")

        try:
            chat_entity = await client.get_entity(CHAT_ID)
        except Exception as e:
            logging.critical(f"Не удалось получить доступ к чату {CHAT_ID}: {e}")
            return

        logging.info("Получение списка администраторов чата...")
        admins = await client.get_participants(chat_entity, filter=ChannelParticipantsAdmins)
        admin_ids = {admin.id for admin in admins}
        logging.info(f"Найдено {len(admin_ids)} администраторов. Они будут проигнорированы.")

        logging.info("Начинаем предварительный анализ участников чата...")

        candidates_to_kick = []
        total_participants = 0
        async for user in client.iter_participants(chat_entity):
            total_participants += 1
            if user.bot or user.id in admin_ids or user.id in legit_users:
                continue
            candidates_to_kick.append(user)

        logging.info(f"Анализ завершен. Всего участников: {total_participants}. Найдено кандидатов на кик: {len(candidates_to_kick)}.")

        if not candidates_to_kick:
            logging.info("Все участники чата есть в базе данных. Зачистка не требуется.")
            return

        if dry_run:
            logging.warning("========================================")
            logging.warning("!!! РЕЖИМ СУХОГО ЗАПУСКА (DRY-RUN) !!!")
            logging.warning("Ниже список тех, кто был бы кикнут:")
            for user in candidates_to_kick:
                 logging.warning(f"[КАНДИДАТ] ID: {user.id}, Имя: {user.first_name}")
            logging.warning("========================================")
            return

        print("\n" + "="*50)
        print(f"ВНИМАНИЕ! Найдено {len(candidates_to_kick)} пользователей для удаления.")
        print("Это действие необратимо.")
        confirm = input("Чтобы продолжить, напишите 'yes' и нажмите Enter: ")
        if confirm.lower() != 'yes':
            logging.info("Зачистка отменена пользователем.")
            return

        logging.info("Подтверждение получено. Начинаю зачистку...")

        kicked_count = 0
        for i, user in enumerate(candidates_to_kick):
            try:
                await client.kick_participant(chat_entity, user.id)
                kicked_count += 1
                logging.info(f"[{kicked_count}/{len(candidates_to_kick)}] Кикнут пользователь {user.id} ({user.first_name}).")

                if kicked_count > 0 and kicked_count % KICK_BATCH_SIZE == 0:
                    logging.warning(f"Достигнут лимит пачки ({KICK_BATCH_SIZE}). Ухожу на перекур на {PAUSE_BETWEEN_BATCHES} секунд...")
                    await asyncio.sleep(PAUSE_BETWEEN_BATCHES)
                else:
                    await asyncio.sleep(random.uniform(MIN_DELAY_BETWEEN_KICKS, MAX_DELAY_BETWEEN_KICKS))

            except FloodWaitError as e:
                logging.warning(f"!!! Пойман FloodWait на {e.seconds} секунд. Ухожу в принудительный сон...")
                await asyncio.sleep(e.seconds + 15)
            except (UserAdminInvalidError, ChatAdminRequiredError):
                logging.critical("ОШИБКА: У вашего аккаунта нет прав на кик участников! Прерываю работу.")
                return
            except Exception as e:
                logging.error(f"Не удалось кикнуть пользователя {user.id}: {e}")

        logging.info("========================================")
        logging.info("Зачистка завершена.")
        logging.info(f"Всего проверено: {total_participants}")
        logging.info(f"Фактически кикнуто: {kicked_count}")
        logging.info("========================================")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Инструмент для зачистки чата от пользователей, отсутствующих в базе данных.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Запустить в режиме симуляции. Никто не будет кикнут, только отображение кандидатов."
    )
    args = parser.parse_args()

    asyncio.run(main(dry_run=args.dry_run, delay=None))
