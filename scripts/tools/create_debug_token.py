import asyncio
import os
import sys
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import database as db

load_dotenv()

async def main():
    await db.init_db()

    admin_ids_str = os.getenv("OWNER_IDS", "")
    user_id = None

    if admin_ids_str:
        try:
            user_id = int(admin_ids_str.split(',')[0].strip())
            print(f"👑 Создаю токен для OWNER ID: {user_id}")
        except:
            pass

    if not user_id:
        print("⚠️ OWNER_IDS не найден или пуст. Ищу любого пользователя в БД...")
        pool = await db.get_db()
        async with pool.acquire() as conn:
            user_id = await conn.fetchval("SELECT user_id FROM users LIMIT 1")

    if not user_id:
        print("❌ В базе данных нет пользователей! Сначала запустите бота и нажмите /start.")
        return

    token = await db.create_web_token(user_id)

    print("\n" + "="*40)
    print(f"✅ ТОКЕН СОЗДАН УСПЕШНО!")
    print(f"👤 User ID: {user_id}")
    print(f"🔑 Token: {token}")
    print("="*40 + "\n")

    with open("/tmp/catdock_debug_token", "w") as f:
        f.write(token)

if __name__ == "__main__":
    asyncio.run(main())
