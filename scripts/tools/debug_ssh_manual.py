import asyncio
import os
import sys
import logging
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import database as db
from utils.ssh_runner import _get_ssh_connection
from utils.server_loader import load_servers_to_cache
from utils import bot_state

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv()

async def main():
    if len(sys.argv) < 2:
        print("Использование: python3 scripts/tools/debug_ssh_manual.py <server_id>")
        print("Пример: python3 scripts/tools/debug_ssh_manual.py de-7")
        return

    server_id = sys.argv[1]

    print(f"🛠 Инициализация БД...")
    await db.init_db()
    
    print(f"🛠 Загрузка серверов в кэш...")
    await load_servers_to_cache()

    if server_id not in bot_state.servers_cache:
        print(f"❌ Сервер '{server_id}' не найден в БД!")
        print("Доступные ID:", ", ".join(bot_state.servers_cache.keys()))
        return

    bot_state.server_states[server_id] = True

    config = bot_state.servers_cache[server_id]
    print(f"\n📋 Конфиг сервера '{server_id}':")
    print(f"   Name: {config.get('name')}")
    print(f"   IP: {config.get('ip')}")
    print(f"   User: {config.get('user')}")
    print(f"   Port: {config.get('check_port', 22)}")
    print(f"   Has Password: {'Yes' if config.get('password') else 'No'}")
    print(f"   Has Key: {'Yes' if config.get('key_path') else 'No'}")
    print("-" * 30)

    print(f"🚀 Попытка подключения через asyncssh (как это делает бот)...")
    
    conn = None
    try:
        
        conn = await _get_ssh_connection(server_id)
        print(f"✅ УСПЕШНО! Соединение установлено.")
        
        print(f"🚀 Тест команды 'whoami'...")
        res = await conn.run("whoami", check=True)
        print(f"   STDOUT: {res.stdout.strip()}")
        
        print(f"🚀 Тест команды 'uptime'...")
        res = await conn.run("uptime", check=True)
        print(f"   STDOUT: {res.stdout.strip()}")
        
        print(f"🚀 Тест команды 'docker ps' (проверка прав)...")
        res = await conn.run("docker ps", check=False)
        if res.exit_status == 0:
             print(f"   STDOUT: Docker работает корректно.")
        else:
             print(f"   STDERR: {res.stderr.strip()}")
             print(f"   ⚠️ Ошибка выполнения docker ps. Код: {res.exit_status}")

    except Exception as e:
        print(f"\n❌ ОШИБКА ПОДКЛЮЧЕНИЯ:")
        print(f"   Тип: {type(e).__name__}")
        print(f"   Сообщение: {str(e)}")
        
        print("\n🔍 Полный Traceback:")
        import traceback
        traceback.print_exc()
        
    finally:
        if conn:
            conn.close()
            await conn.wait_closed()
            print("\n🔌 Соединение закрыто.")

if __name__ == "__main__":
    asyncio.run(main())
