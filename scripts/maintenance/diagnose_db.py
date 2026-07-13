import asyncio
import os
import sys
import logging
from dotenv import load_dotenv
import asyncpg

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def main():
    print("🔍 ЗАПУСК ДИАГНОСТИКИ БАЗЫ ДАННЫХ...")

    load_dotenv()
    pg_host = os.getenv("PG_HOST", "localhost")
    pg_user = os.getenv("PG_USER")
    pg_pass = os.getenv("PG_PASS")
    pg_name = os.getenv("PG_NAME")
    
    print(f"📋 Конфигурация: {pg_host}:{os.getenv('PG_PORT', 5432)} (DB: {pg_name}, User: {pg_user})")

    if not all([pg_user, pg_pass, pg_name]):
        print("❌ ОШИБКА: Не все переменные БД указаны в .env!")
        return

    try:
        conn = await asyncpg.connect(
            user=pg_user,
            password=pg_pass,
            database=pg_name,
            host=pg_host,
            port=os.getenv("PG_PORT", 5432)
        )
        print("✅ Подключение к БД успешно!")
    except Exception as e:
        print(f"❌ ОШИБКА ПОДКЛЮЧЕНИЯ: {e}")
        print("💡 Совет: Убедитесь, что контейнер catdock_db запущен (docker ps).")
        return

    try:
        print("\n📊 Статистика таблиц:")
        
        tables = ['users', 'user_containers', 'support_tickets', 'promo_codes']
        total_rows = 0
        
        for table in tables:
            try:
                count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
                print(f"   • {table}: {count} записей")
                total_rows += count
            except asyncpg.UndefinedTableError:
                print(f"   • {table}: ⚠️ ТАБЛИЦА НЕ НАЙДЕНА (Миграции не применены?)")
            except Exception as e:
                print(f"   • {table}: Ошибка ({e})")

        print("-" * 30)
        if total_rows == 0:
            print("⚠️  БАЗА ДАННЫХ ПУСТА! (Все таблицы имеют 0 записей)")
            print("   Вероятные причины:")
            print("   1. Был выполнен 'docker-compose down -v' (удаление томов).")
            print("   2. Поврежден файл тома Docker.")
            print("   3. Подключение идет к другой (новой) базе.")
        else:
            print(f"✅ База данных жива. Всего записей: {total_rows}")
            print("   Если в боте 'нули', попробуйте перезагрузить его: 'RH restart'")

    finally:
        await conn.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Прервано.")
