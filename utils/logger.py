import logging
import os
import sys
from logging.handlers import RotatingFileHandler

def setup_logger():
    """
    Настраивает логирование:
    1. Создает папку logs/
    2. Пишет в файл catdock.log (с ротацией)
    3. Выводит в консоль
    4. Глушит лишний шум от библиотек
    """
    log_dir = "logs"
    log_file = "catdock.log"
    log_path = os.path.join(log_dir, log_file)
    
    os.makedirs(log_dir, exist_ok=True)

    if not os.path.exists(log_path):
        with open(log_path, 'w', encoding='utf-8') as f:
            pass

    log_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")

    file_handler = RotatingFileHandler(
        log_path, 
        maxBytes=10*1024*1024, 
        backupCount=5, 
        encoding="utf-8"
    )
    file_handler.setFormatter(log_formatter)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_formatter)

    logging.basicConfig(
        level=logging.INFO, 
        handlers=[file_handler, console_handler], 
        force=True
    )

    logging.getLogger('asyncssh').setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("apscheduler.executors.default").setLevel(logging.WARNING)
    logging.getLogger("apscheduler.scheduler").setLevel(logging.WARNING)
    logging.getLogger("multipart").setLevel(logging.WARNING)

    logging.info("✅ Логирование настроено.")
