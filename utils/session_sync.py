import logging
import os
import asyncssh
from .ssh_runner import run_command_on_server, _get_ssh_connection
from config import SERVERS
import settings 

async def copy_session_from_container(server_id: str, container_name: str, container_session_path: str, local_destination_path: str):
    server_config = SERVERS.get(server_id)
    if not server_config:
        logging.error(f"[SESSION_SYNC] Не найдена конфигурация для сервера {server_id}")
        return

    try:
        if server_config.get('local'):
            docker_cp_command = f"docker cp {container_name}:{container_session_path} {local_destination_path}"
            await run_command_on_server(server_id, docker_cp_command)
            logging.info(f"[SESSION_SYNC] Локально скопирована сессия: {container_name} -> {local_destination_path}")

        else:
            temp_filename = f"{container_name}_{os.path.basename(container_session_path)}"
            remote_temp_path = f"/tmp/{temp_filename}"

            docker_cp_command = f"docker cp {container_name}:{container_session_path} {remote_temp_path}"
            await run_command_on_server(server_id, docker_cp_command)

            async with await _get_ssh_connection(server_id) as conn:
                await asyncssh.scp((conn, remote_temp_path), local_destination_path)

            cleanup_command = f"rm {remote_temp_path}"
            await run_command_on_server(server_id, cleanup_command)

            logging.info(f"[SESSION_SYNC] Удаленно скопирована сессия: {container_name} -> {local_destination_path}")

    except Exception as e:
        logging.error(f"[SESSION_SYNC] Ошибка при копировании сессии для {container_name}: {e}", exc_info=True)
