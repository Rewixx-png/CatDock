import asyncio
import sys
import logging
import json
import uvicorn
import sentry_sdk
from datetime import datetime
from sentry_sdk.integrations.aiohttp import AioHttpIntegration
from apscheduler.events import JobExecutionEvent, EVENT_JOB_ERROR
from aiogram.types import BotCommand, BotCommandScopeDefault

from loader import bot, dp, scheduler, storage 
from broker import broker

from config import TOKEN, BOT_VERSION, SENTRY_DSN
from utils.logger import setup_logger
from utils import bot_state
import database as db
import settings
import lexicon

from api import setup_api_server
from handlers import routers_list
from handlers.common.errors_handler import handle_errors

from middlewares.maintenance import MaintenanceMiddleware
from middlewares.block_middleware import BlockMiddleware

from middlewares.logging_middleware import GlobalLoggingMiddleware 

import utils.worker_tasks
from utils.server_loader import load_servers_to_cache
from utils.jobs import (
    tick_containers, cleanup_old_container_logs,
    check_expiring_containers, sync_frozen_containers_state, send_db_backup,
    sync_sessions_to_host, update_server_statuses_cache,
    send_hourly_server_report, check_web_loading_status,
    collect_server_metrics, check_restart_loops,
    cleanup_notifications_job
)

bot_state.bot_start_time = datetime.now()

async def scheduler_error_listener(event: JobExecutionEvent):
    if event.exception:
        logging.error(f"Job {event.job_id} failed: {event.exception}")
    else:
        logging.warning(f"Job {event.job_id} errored (no exception info)")


async def setup_bot_commands(bot_instance):
    commands = [
        BotCommand(command="start", description="Главное меню"),
        BotCommand(command="help", description="Справка по командам"),
        BotCommand(command="status", description="Статус серверов"),
        BotCommand(command="ping", description="Проверка связи"),
        BotCommand(command="top", description="Топ пользователей"),
        BotCommand(command="login", description="Веб-панель")
    ]
    try:
        await bot_instance.set_my_commands(commands, scope=BotCommandScopeDefault())
        logging.info("✅ Команды бота установлены (скрыт /profile).")
    except Exception as e:
        logging.error(f"Ошибка установки команд: {e}")

async def on_startup():
    print("\n" + "="*50)
    logging.info("CATDOCK")
    print("="*50 + "\n")

    await db.init_db()
    await load_servers_to_cache()

    await lexicon.sync_lexicon()

    db_admins = await db.get_all_admin_ids()
    bot_state.admin_ids_cache.update(db_admins)

    states_from_db_json = await db.get_bot_setting('server_states')
    if states_from_db_json:
        try:
            states_from_db = json.loads(states_from_db_json)
            for s_id in bot_state.servers_cache:
                if s_id in states_from_db:
                    bot_state.servers_cache[s_id]['active'] = states_from_db[s_id]
            bot_state.server_states = {sid: sdata.get('active', True) for sid, sdata in bot_state.servers_cache.items()}
        except Exception as e:
            logging.error(f"Error loading server states: {e}")

    try:
        bot_state.set_bot_instance(bot)
        bot_state.bot_info_cache = await bot.get_me()
        logging.info(f"Authorized as @{bot_state.bot_info_cache.username}")
        await setup_bot_commands(bot)
    except Exception as e:
        logging.critical(f"❌ API Error: {e}")
        exit(1)

    await broker.startup()

async def main():
    if not TOKEN:
        print("CRITICAL: Токен бота не найден! Проверьте файл .env.")
        return

    setup_logger()

    if SENTRY_DSN:
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            traces_sample_rate=1.0,
            profiles_sample_rate=1.0,
            environment="production",
            integrations=[AioHttpIntegration()]
        )
        print("✅ Sentry Integrated!")

    await on_startup()

    dp.errors.register(handle_errors)
    dp.update.outer_middleware(MaintenanceMiddleware())
    dp.update.outer_middleware(BlockMiddleware())
    dp.update.outer_middleware(GlobalLoggingMiddleware()) 

    dp.include_routers(*routers_list)

    scheduler.add_listener(scheduler_error_listener, EVENT_JOB_ERROR)

    scheduler.add_job(update_server_statuses_cache, 'interval', minutes=settings.SCHED_UPDATE_STATUS_INTERVAL, args=(bot,), id='status_cache_updater')
    scheduler.add_job(collect_server_metrics, 'interval', minutes=10, args=(bot,), id='metrics_collector')

    scheduler.add_job(tick_containers, 'interval', minutes=settings.SCHED_TICK_CONTAINERS_INTERVAL, args=(bot,))
    scheduler.add_job(check_expiring_containers, 'cron', hour='*', args=(bot,))
    scheduler.add_job(cleanup_old_container_logs, 'cron', hour=4, minute=0)
    scheduler.add_job(sync_frozen_containers_state, 'interval', minutes=settings.SCHED_SYNC_FROZEN_INTERVAL, args=(bot,))
    scheduler.add_job(send_db_backup, 'interval', hours=1, args=(bot,))
    scheduler.add_job(sync_sessions_to_host, 'interval', minutes=settings.SCHED_SYNC_SESSIONS_INTERVAL, args=(bot,))
    scheduler.add_job(send_hourly_server_report, 'interval', hours=1, args=(bot,))
    scheduler.add_job(check_web_loading_status, 'interval', seconds=10, args=(bot,))

    scheduler.add_job(cleanup_notifications_job, 'cron', hour=3, minute=30, args=(bot,), id='notif_cleaner')

    scheduler.add_job(check_restart_loops, 'interval', minutes=1, args=(bot,), id='boot_loop_checker')

    scheduler.start()

    no_web = "--no-web" in sys.argv
    web_port = 8082
    try:
        port_idx = sys.argv.index("--port")
        web_port = int(sys.argv[port_idx + 1])
    except (ValueError, IndexError):
        pass

    await bot.delete_webhook(drop_pending_updates=True)

    try:
        if no_web:
            await dp.start_polling(bot)
        else:
            api_app = setup_api_server(bot)
            config = uvicorn.Config(app=api_app, host="0.0.0.0", port=web_port, log_level="warning")
            server = uvicorn.Server(config)
            logging.info(f"Web server on port {web_port}")
            await asyncio.gather(server.serve(), dp.start_polling(bot))

    finally:
        await broker.shutdown()
        if storage: await storage.close()
        if scheduler.running: scheduler.shutdown()
        await bot.session.close()
        logging.info("Bot stopped.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Выключение бота по команде.")
