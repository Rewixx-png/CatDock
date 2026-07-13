import asyncio
import logging
import typing
import os
from .ssh_runner import run_command_on_server
from config import IMAGES
from utils import bot_state

ASSETS_BASE_URL = "https://raw.githubusercontent.com/Rewixx-png/cat-host-assets/main/docker"

GIT_REPOS = {
    'rewheroku': 'https://github.com/Rewixx-png/RewHeroku',
    'heroku': 'https://github.com/coddrago/Heroku',
    'hikka': 'https://github.com/beveiled/hikka',
    'foxuserbot': 'https://github.com/FoxUserbot/FoxUserbot',
    'legacy': 'https://github.com/Crayz310/Legacy'
}

CLONE_FOLDERS = {
    'rewheroku': 'rewheroku_src',
    'heroku': 'heroku_src',
    'hikka': 'hikka_src',
    'foxuserbot': 'foxuserbot_src',
    'legacy': 'legacy_src'
}

ASSET_FOLDERS = {
    'rewheroku': 'RewHeroku',
    'heroku': 'Heroku',
    'hikka': 'Hikka',
    'foxuserbot': 'FoxUserbot',
    'legacy': 'Legacy'
}

async def update_docker_image_from_git(
    server_id: str, 
    image_id: str, 
    progress_callback: typing.Callable
) -> tuple[bool, str]:

    if image_id not in GIT_REPOS:
        return False, f"Image_id '{image_id}' не настроен."

    server_config = bot_state.servers_cache.get(server_id)
    if not server_config:
        return False, f"Сервер {server_id} не найден в кэше."

    folder_name = CLONE_FOLDERS[image_id]
    image_name = IMAGES[image_id]['image_name']
    asset_folder = ASSET_FOLDERS[image_id]

    base_build_dir = "/root/Builds"
    remote_folder_path = f"{base_build_dir}/{folder_name}"

    dockerfile_url = f"{ASSETS_BASE_URL}/{asset_folder}/Dockerfile"
    entrypoint_url = f"{ASSETS_BASE_URL}/{asset_folder}/entrypoint.sh"

    try:
        await progress_callback(f"Подготовка папки `{remote_folder_path}`...")

        cleanup_cmd = f"rm -rf {remote_folder_path} && mkdir -p {remote_folder_path}"
        await run_command_on_server(server_id, cleanup_cmd)

        await progress_callback(f"Скачивание конфигов с GitHub...")

        curl_cmd = (
            f"curl -Lfs -o {remote_folder_path}/Dockerfile {dockerfile_url} && "
            f"curl -Lfs -o {remote_folder_path}/entrypoint.sh {entrypoint_url} && "
            f"chmod +x {remote_folder_path}/entrypoint.sh"
        )

        res = await run_command_on_server(server_id, curl_cmd)
        if res.exit_status != 0:
            raise Exception(f"Не удалось скачать файлы с GitHub. Проверь ссылки!\nОшибка: {res.stderr}")

        await progress_callback(f"Сборка образа `{image_name}` (git clone внутри)...")

        build_command = f"docker build --no-cache -t {image_name} {remote_folder_path}"

        result = await run_command_on_server(server_id, build_command, timeout=1500)

        if result.exit_status != 0:
            raise Exception(f"Build failed: {result.stderr}")

        success_message = f"Образ `{image_name}` успешно обновлен!"
        logging.info(f"Сборка {image_name} на {server_id} завершена.\n{result.stdout}")

        await run_command_on_server(server_id, f"rm -rf {remote_folder_path}")

        return True, success_message

    except Exception as e:
        error_message = f"Ошибка обновления `{image_name}` на `{server_id}`."
        if hasattr(e, 'stderr') and e.stderr:
            error_details = e.stderr.strip()
            error_message += f"\n<pre><code>{error_details}</code></pre>"
        else:
            error_message += f"\n<code>{e}</code>"

        logging.error(f"{error_message}", exc_info=True)
        return False, error_message
