import os
import shutil
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "../../"))

def remove_directory(path):
    if os.path.exists(path):
        try:
            shutil.rmtree(path)
            print(f"✅ Удалена папка: {path}")
        except Exception as e:
            print(f"❌ Ошибка удаления {path}: {e}")
    else:
        print(f"⚠️ Папка не найдена (уже чиста): {path}")

def remove_file(path):
    if os.path.exists(path):
        try:
            os.remove(path)
            print(f"✅ Удален файл: {path}")
        except Exception as e:
            print(f"❌ Ошибка удаления {path}: {e}")

def clean_pycache(root_dir):
    print("🧹 Поиск и удаление __pycache__...")
    count = 0
    for root, dirs, files in os.walk(root_dir):
        for d in dirs:
            if d == "__pycache__":
                full_path = os.path.join(root, d)
                try:
                    shutil.rmtree(full_path)
                    count += 1
                except Exception as e:
                    print(f"Ошибка удаления {full_path}: {e}")
    
    if count > 0:
        print(f"🔥 Удалено {count} папок __pycache__")
    else:
        print("✨ __pycache__ не найдены.")

def main():
    print(f"🗑️ ЗАПУСК ОЧИСТКИ CATDOCK [Root: {PROJECT_ROOT}]")
    print("-" * 50)

    archive_path = os.path.join(PROJECT_ROOT, "_archive")
    remove_directory(archive_path)

    install_log = os.path.join(PROJECT_ROOT, "install.log")
    remove_file(install_log)

    clean_pycache(PROJECT_ROOT)

    print("-" * 50)
    print("🏁 Очистка завершена. Мусор вынесен.")

if __name__ == "__main__":
    main()
