import os
from config import PROJECT_ROOT

LOCAL_SESSIONS_DIR = os.path.join(PROJECT_ROOT, "Session")
STORAGE_DIR = os.path.join(PROJECT_ROOT, "storage")
LOCALES_CACHE_DIR = os.path.join(STORAGE_DIR, "locales")

VIP_USER_IDS = []

SYSTEM_CONTAINERS_LIST = [
    'catdock_db', 
    'catdock-db', 
    'catdock_redis', 
    'catdock-redis', 
    'CatDock', 
    'catdock_bot',
    'catdock_worker'
]



DOCKER_ASSETS_BASE_URL = os.getenv("DOCKER_ASSETS_BASE_URL", "")
LOCALES_REPO_URL = os.getenv("LOCALES_REPO_URL", "")

SUPPORTED_LANGUAGES = ["ru", "en", "uk"]

LOCALE_FILES = [
    "admin", "buttons", "common", "containers", 
    "errors", "finance", "profile"
]

AUTH_TOKEN_LIFETIME = 300           
LOGIN_CODE_LIFETIME = 300           
TRANSFER_TOKEN_LIFETIME = 900       
CAPTCHA_TIMEOUT = 300               
INTERACTIVE_SESSION_TIMEOUT = 1800  

SCHED_UPDATE_STATUS_INTERVAL = 1
SCHED_TICK_CONTAINERS_INTERVAL = 1
SCHED_SYNC_FROZEN_INTERVAL = 5
SCHED_SYNC_SESSIONS_INTERVAL = 10

ALLOCATOR_MIN_RAM_MB = 1024          
ALLOCATOR_RAM_BUFFER_MB = 200        
SLOT_NOTIFICATION_COOLDOWN = 3600    

# Compatibility defaults for RewHost features removed from CatDock.  Keeping
# them at zero disables leveling discounts/XP without breaking shared pricing
# and notification helpers which still read these settings.
LEVEL_MIN_MSG_LEN = 1
LEVEL_CHAT_COOLDOWN = 0
LEVEL_XP_PER_MESSAGE = 0
LEVEL_XP_PER_RUBLE = 0
LEVEL_DISCOUNT_PER_LEVEL = 0
LEVEL_MAX_DISCOUNT = 100
EXCLUDED_FROM_TOP = []

NEWS_CHAT_USERNAME = os.getenv("NEWS_CHAT_USERNAME")
PROMO_TOPIC_ID = None
