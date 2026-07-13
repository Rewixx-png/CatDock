import os
import sys
import subprocess
import asyncio
from dotenv import load_dotenv

load_dotenv()

PG_USER = os.getenv("PG_USER", "catdock_user")
PG_NAME = os.getenv("PG_NAME", "catdock_db")
CONTAINER_NAME = "catdock_db" 

def restore(backup_path):
    if not os.path.exists(backup_path):
        print(f"❌ Файл не найден: {backup_path}")
        return

    print(f"⚠️  ВНИМАНИЕ! Вы собираетесь восстановить БД из файла: {backup_path}")
    print(f"⚠️  ВСЕ ТЕКУЩИЕ ДАННЫЕ В '{PG_NAME}' БУДУТ ПЕРЕЗАПИСАНЫ/ДОПОЛНЕНЫ.")
    print(f"🎯 Целевой контейнер: {CONTAINER_NAME}")
    
    confirm = input("Вы уверены? Напишите 'YES' для продолжения: ")
    if confirm != "YES":
        print("Отмена.")
        return

    print("\n🚀 Запуск восстановления...")

    cmd = f"cat {backup_path} | docker exec -i {CONTAINER_NAME} psql -U {PG_USER} -d {PG_NAME}"
    
    try:
        
        result = subprocess.run(cmd, shell=True, check=True, stderr=subprocess.PIPE)
        print("✅ Восстановление завершено успешно!")
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка восстановления (Код {e.returncode}):")
        print(e.stderr.decode())

def main():
    if len(sys.argv) < 2:
        print("Использование: python3 scripts/maintenance/restore_db.py <файл_бэкапа.sql>")
        return
    
    backup_file = sys.argv[1]
    restore(backup_file)

if __name__ == "__main__":
    main()
