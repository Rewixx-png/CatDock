import asyncio
import logging
import random
import re
import os
from utils.ssh_runner import run_command_on_server
from config import SERVERS, DEFAULT_CPU_LIMIT
from .inspector import get_container_status
from .compose_generator import generate_compose_config

BASE_CONTAINERS_DIR = "/var/lib/catdock/containers"

IMAGE_FIXES = {
    'heroku': {
        'command': ["python3", "-m", "heroku", "--root", "--data-root", "/user_data"] 
    },
    'rewheroku': {
        'command': ["python3", "-m", "rewheroku", "--root", "--data-root", "/user_data"]
    },
    'legacy': {
        'command': ["python3", "-m", "legacy", "--root", "--data-root", "/user_data"]
    },
    'foxuserbot': {
        'command': ["python3", "-m", "fox_userbot", "--root", "--data-root", "/user_data"]
    },
    'hikka': {
        'command': ["python3", "-m", "hikka", "--root", "--data-root", "/user_data"]
    }
}

async def rename_container(server_id: str, old_name: str, new_name: str):
    try:
        old_path = f"{BASE_CONTAINERS_DIR}/{old_name}"
        new_path = f"{BASE_CONTAINERS_DIR}/{new_name}"

        await run_command_on_server(server_id, f"cd {old_path} && docker compose down")
        await run_command_on_server(server_id, f"mv {old_path} {new_path}")

        sed_cmd = f"sed -i 's/container_name: {old_name}/container_name: {new_name}/g' {new_path}/docker-compose.yml"
        await run_command_on_server(server_id, sed_cmd)

        await run_command_on_server(server_id, f"cd {new_path} && docker compose up -d")

    except Exception as e:
        logging.error(f"Rename error {old_name}->{new_name}: {e}")
        raise e

async def _safe_ufw_allow(server_id: str, port: str | int):
    try:
        await run_command_on_server(server_id, f"ufw allow {port}/tcp")
    except Exception as e:
        if "127" not in str(e):
            logging.warning(f"UFW allow failed on {server_id}: {e}")

async def _safe_ufw_delete(server_id: str, port: str | int):
    try:
        await run_command_on_server(server_id, f"ufw delete allow {port}/tcp")
    except Exception as e:
        if "127" not in str(e):
            logging.warning(f"UFW delete failed on {server_id}: {e}")

async def delete_container(server_id: str, container_name: str):
    container_dir = f"{BASE_CONTAINERS_DIR}/{container_name}"

    try:
        res = await run_command_on_server(server_id, f"docker inspect --format='{{{{(index .HostConfig.PortBindings \\\"8080/tcp\\\") 0 \\\"HostPort\\\"}}}}' {container_name}", check=False)
        port = res.stdout.strip()

        await run_command_on_server(server_id, f"cd {container_dir} && docker compose down", check=False)
        await run_command_on_server(server_id, f"docker rm -f {container_name}", check=False)
        await run_command_on_server(server_id, f"rm -rf {container_dir}")

        if port.isdigit():
            await _safe_ufw_delete(server_id, port)

    except Exception as e:
        if "No such" not in str(e):
            logging.error(f"Delete error for {container_name}: {e}")
            raise e

async def _sanitize_new_container(server_id: str, container_name: str):
    logging.info(f"🧹 Sanitizing {container_name} on {server_id}...")

    for _ in range(10):
        status = await get_container_status(server_id, container_name)
        if status == 'running':
            break
        await asyncio.sleep(1)

    cleanup_cmds = [
        f"docker exec {container_name} find /user_data -name '*.session' -delete",
        f"docker exec {container_name} find /data -name '*.session' -delete", 
        f"docker exec {container_name} rm -rf /user_data/session.string",
    ]
    for cmd in cleanup_cmds:
        await run_command_on_server(server_id, cmd, check=False)

async def _boost_and_revert_cpu(server_id: str, container_name: str, target_cpu_limit: float):
    try:
        await run_command_on_server(server_id, f"docker update --cpus=\"2.0\" {container_name}", check=False)

        await asyncio.sleep(20)

        await run_command_on_server(server_id, f"docker update --cpus=\"{target_cpu_limit}\" {container_name}", check=False)
    except Exception as e:
        logging.error(f"CPU Boost Error for {container_name}: {e}")

async def create_container(user_id: int, username: str | None, server_id: str, tariff: dict, image: dict, forced_name: str | None = None):
    server_ip = SERVERS[server_id]['ip']
    MAX_RETRIES = 5
    last_exception = None

    img_name_lower = image['image_name'].lower()
    fix_config = {}

    for key, conf in IMAGE_FIXES.items():
        if key in img_name_lower:
            fix_config = conf
            break

    if not fix_config:
        fix_config = {
             'command': ["python3", "-m", "heroku", "--root", "--data-root", "/user_data"]
        }

    for attempt in range(1, MAX_RETRIES + 1):
        retry_allowed = True
        if forced_name:
            container_name = forced_name
            retry_allowed = False
            try: await delete_container(server_id, forced_name)
            except: pass
        else:
            safe_username = re.sub(r'[^a-zA-Z0-9]', '', (username or str(user_id)).lower())[:10]
            container_name = f"cat-{safe_username or user_id}-{''.join(random.choice('abcdefghijklmnopqrstuvwxyz0123456789') for _ in range(6))}"

        public_port = random.randint(10000, 30000)
        target_cpu = DEFAULT_CPU_LIMIT
        ram_mb = tariff.get('ram_mb', 300)

        container_dir = f"{BASE_CONTAINERS_DIR}/{container_name}"

        try:
            await _safe_ufw_allow(server_id, public_port)

            await run_command_on_server(server_id, f"mkdir -p {container_dir}/data")

            compose_content = generate_compose_config(
                container_name=container_name,
                image_name=image['image_name'],
                port=public_port,
                mem_limit=ram_mb,
                cpu_limit="2.0",
                command=fix_config.get('command'),
                working_dir=fix_config.get('working_dir')
            )

            write_cmd = f"cat > {container_dir}/docker-compose.yml << 'EOF'\n{compose_content}\nEOF"
            await run_command_on_server(server_id, write_cmd)

            start_cmd = f"cd {container_dir} && docker compose up -d"
            result = await run_command_on_server(server_id, start_cmd, check=False)

            if result.exit_status == 0:
                logging.info(f"Container {container_name} created. Port: {public_port}")
                await _sanitize_new_container(server_id, container_name)

                asyncio.create_task(_boost_and_revert_cpu(server_id, container_name, target_cpu))

                return container_name, public_port, f"http://{server_ip}:{public_port}"
            else:
                await _safe_ufw_delete(server_id, public_port)
                await run_command_on_server(server_id, f"rm -rf {container_dir}")

                error_msg = f"Compose Error: {result.stderr.strip()}"
                last_exception = Exception(error_msg)
                if not retry_allowed: raise last_exception
                continue

        except Exception as e:
            logging.error(f"Creation failed: {e}")
            last_exception = e
            if not retry_allowed: raise e

    if last_exception:
        raise last_exception

    return None, None, None
