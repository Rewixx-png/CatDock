import json
import os
import logging
import aiohttp
import asyncio
from config import PROJECT_ROOT
import settings

FACTORY_LOCALES_DIR = os.path.join(PROJECT_ROOT, 'locales') 
CACHE_LOCALES_DIR = settings.LOCALES_CACHE_DIR            

LEXICON: dict[str, dict[str, str]] = {
    'ru': {},
    'en': {},
    'uk': {},
}

def _load_from_dir(directory: str):
    """Читает JSON-файлы из указанной директории и обновляет LEXICON."""
    global LEXICON
    if not os.path.exists(directory):
        return

    for lang in settings.SUPPORTED_LANGUAGES:
        lang_path = os.path.join(directory, lang)

        if os.path.isdir(lang_path):
            for filename in os.listdir(lang_path):
                if filename.endswith(".json"):
                    file_path = os.path.join(lang_path, filename)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            LEXICON[lang].update(data)
                    except Exception as e:
                        logging.error(f"❌ Failed to load locale {lang}/{filename}: {e}")

        elif os.path.exists(lang_path + ".json"):
            try:
                with open(lang_path + ".json", 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    LEXICON[lang].update(data)
            except Exception as e:
                logging.error(f"❌ Failed to load legacy locale {lang}.json: {e}")

def load_lexicon():
    """
    Загружает лексикон.
    Приоритет:
    1. Кэш (storage/locales) - самые свежие файлы.
    2. Заводские (locales/) - если кэша нет или ключи отсутствуют.
    """
    
    _load_from_dir(FACTORY_LOCALES_DIR)

    _load_from_dir(CACHE_LOCALES_DIR)

    logging.info(f"📚 Lexicon loaded. RU keys: {len(LEXICON['ru'])}, EN: {len(LEXICON['en'])}")

async def sync_lexicon():
    """
    Асинхронно скачивает актуальные файлы переводов с GitHub
    и сохраняет их в storage/locales.
    """
    logging.info("🌍 Syncing lexicon from GitHub...")
    os.makedirs(CACHE_LOCALES_DIR, exist_ok=True)
    
    updated_count = 0
    errors_count = 0

    async with aiohttp.ClientSession() as session:
        for lang in settings.SUPPORTED_LANGUAGES:
            lang_dir = os.path.join(CACHE_LOCALES_DIR, lang)
            os.makedirs(lang_dir, exist_ok=True)

            for filename in settings.LOCALE_FILES:
                url = f"{settings.LOCALES_REPO_URL}/{lang}/{filename}.json"
                target_path = os.path.join(lang_dir, f"{filename}.json")
                
                try:
                    async with session.get(url) as response:
                        if response.status == 200:
                            content = await response.read()
                            
                            try:
                                json.loads(content)
                                with open(target_path, "wb") as f:
                                    f.write(content)
                                updated_count += 1
                            except json.JSONDecodeError:
                                logging.error(f"⚠️ Invalid JSON from GitHub: {url}")
                                errors_count += 1
                        else:
                            
                            pass
                except Exception as e:
                    logging.warning(f"Failed to download {url}: {e}")
                    errors_count += 1
    
    if updated_count > 0:
        logging.info(f"✅ Lexicon updated: {updated_count} files downloaded. Reloading...")
        load_lexicon()
    else:
        logging.info("ℹ️ Lexicon sync finished (no new files or error).")

load_lexicon()
