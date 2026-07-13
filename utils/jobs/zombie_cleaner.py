import logging
import asyncio
from aiogram import Bot
from config import SERVERS, LOG_CHAT_ID
from utils.ssh_runner import run_command_on_server
from utils import bot_state
import settings

async def clean_zombies_globally(bot: Bot):
    logging.info("🔥 ZombieCleaner: Запуск протокола 'Phoenix' (Restart)...")

    errors = []
    total_restarted = 0

    remote_script = f"""
    TARGETS=$(docker stats --no-stream --format "{{{{.Name}}}} {{{{.PIDs}}}}" | grep "^cat-" | awk '$2 > 200 {{print $1}}')

    if [ -z "$TARGETS" ]; then
        echo "CLEAN"
        exit 0
    fi

    echo "RESTARTING: $TARGETS"

    for CONT in $TARGETS; do
        docker restart -t 10 $CONT
    done

    echo "DONE"
    """

    for server_id, server_info in SERVERS.items():
        if not bot_state.server_states.get(server_id, True):
            continue

        try:
            result = await run_command_on_server(server_id, remote_script, timeout=120)

            if result.exit_status != 0:
                raise Exception(f"Script error: {result.stderr}")

            if "RESTARTING" in result.stdout:
                lines = result.stdout.strip().splitlines()
                restarted_line = next((l for l in lines if l.startswith("RESTARTING:")), "")
                count = len(restarted_line.split()) - 1 

                if count > 0:
                    total_restarted += count
                    logging.info(f"♻️ ZombieCleaner: На сервере {server_id} перезагружено {count} контейнеров.")

                    if LOG_CHAT_ID:
                        conts_list = restarted_line.replace("RESTARTING:", "").strip()
                        await bot.send_message(
                            LOG_CHAT_ID,
                            f"♻️ <b>Авто-Рестарт (Зомби)</b>\n"
                            f"Сервер: <b>{server_info['name']}</b>\n"
                            f"Контейнеры переполнились процессами (>200) и были перезагружены:\n"
                            f"<code>{conts_list}</code>",
                            parse_mode="HTML"
                        )

        except Exception as e:
            error_msg = f"⚠️ <b>ZombieCleaner Error</b>\nServer: <b>{server_info['name']}</b>\n<code>{str(e)}</code>"
            logging.error(f"ZombieCleaner failed on {server_id}: {e}")
            errors.append(error_msg)

    if errors and LOG_CHAT_ID:
        report = "\n\n".join(errors)
        try:
            await bot.send_message(
                chat_id=LOG_CHAT_ID,
                text=f"🧟 <b>ОШИБКИ ZOMBIE CLEANER</b>\n\n{report}",
                parse_mode="HTML"
            )
        except Exception:
            pass

    if total_restarted > 0:
        logging.info(f"🔥 ZombieCleaner: Всего перезагружено {total_restarted} контейнеров.")
