import os
import re
import requests
from PIL import Image
from io import BytesIO
import logging
from config import PROJECT_ROOT

FLAGS_CACHE_DIR = os.path.join(PROJECT_ROOT, "storage", "flags")
os.makedirs(FLAGS_CACHE_DIR, exist_ok=True)

CUSTOM_FLAG_MAP = {
    'SP': 'es', 
    'UK': 'gb', 
    'EN': 'gb', 
    'US': 'us', 
    'DE': 'de', 
    'FI': 'fi', 
    'FR': 'fr', 
    'NL': 'nl', 
    'PL': 'pl', 
    'UA': 'ua', 
    'RU': 'ru', 
    'KZ': 'kz', 
    'BY': 'by', 
}

def extract_and_clean_name(server_name: str) -> tuple[str, str]:
    """
    1. Очищает имя от эмодзи.
    2. Определяет код страны (с учетом кастомного маппинга).
    Example: "SP-1 (High Ram)" -> ("es", "SP-1 (High Ram)")
    """
    if not server_name:
        return "un", "Unknown"

    clean_name = server_name.encode('ascii', 'ignore').decode('ascii').strip()
    clean_name = re.sub(r'\s+', ' ', clean_name)

    parts = clean_name.replace('_', '-').split('-')
    if not parts or not parts[0]:
        parts = clean_name.split(' ')

    if parts and len(parts[0]) >= 2:
        raw_code = parts[0][:2].upper()

        if raw_code.isalpha():
            
            code = CUSTOM_FLAG_MAP.get(raw_code, raw_code).lower()
        else:
            code = "un"
    else:
        code = "un" 

    return code, clean_name

def get_flag_image(country_code: str, height: int = 20) -> Image.Image | None:
    """
    Возвращает PIL Image флага.
    Сначала ищет в storage/flags/, если нет - качает с flagcdn.
    """
    if not country_code or len(country_code) != 2:
        return None

    country_code = country_code.lower()
    local_path = os.path.join(FLAGS_CACHE_DIR, f"{country_code}.png")

    if os.path.exists(local_path):
        try:
            img = Image.open(local_path).convert("RGBA")
            return _resize_flag(img, height)
        except Exception as e:
            logging.error(f"Error loading cached flag {country_code}: {e}")
            
            try: os.remove(local_path)
            except: pass
            return None

    url = f"https://flagcdn.com/w160/{country_code}.png"
    try:
        response = requests.get(url, timeout=3)
        if response.status_code == 200:
            img_data = BytesIO(response.content)
            img = Image.open(img_data).convert("RGBA")

            with open(local_path, "wb") as f:
                f.write(response.content)

            return _resize_flag(img, height)
        else:
            logging.warning(f"Flag not found for code '{country_code}' (HTTP {response.status_code})")
            return None
    except Exception as e:
        logging.error(f"Failed to download flag {country_code}: {e}")
        return None

def _resize_flag(img: Image.Image, target_height: int) -> Image.Image:
    """Пропорциональное изменение размера"""
    aspect_ratio = img.width / img.height
    new_width = int(target_height * aspect_ratio)
    return img.resize((new_width, target_height), Image.Resampling.LANCZOS)
