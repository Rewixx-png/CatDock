import os
import sys
import logging
from taskiq import TaskiqEvents
from taskiq_redis import ListQueueBroker, RedisAsyncResultBackend
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = os.getenv("REDIS_PORT", "6379")
REDIS_DB = os.getenv("REDIS_DB", "0")

REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"

result_backend = RedisAsyncResultBackend(
    redis_url=REDIS_URL,
)

broker = ListQueueBroker(
    url=REDIS_URL,
).with_result_backend(result_backend)

@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def on_startup(state):
    import database as db
    from utils.server_loader import load_servers_to_cache
    import sentry_sdk
    from config import SENTRY_DSN

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logging.getLogger('asyncssh').setLevel(logging.WARNING)

    logging.info("👷 Worker: Starting up...")

    if SENTRY_DSN:
        try:
            sentry_sdk.init(dsn=SENTRY_DSN, traces_sample_rate=1.0)
            logging.info("✅ Worker Sentry enabled.")
        except Exception as e:
            logging.error(f"Worker Sentry init failed: {e}")

    try:
        await db.init_db()
        logging.info("✅ Worker DB connected.")

        await load_servers_to_cache()
        logging.info("✅ Worker Servers loaded.")
    except Exception as e:
        logging.critical(f"❌ Worker Startup Error: {e}", exc_info=True)

@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def on_shutdown(state):
    logging.info("👷 Worker: Shutting down...")

import utils.worker_tasks
