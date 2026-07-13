import asyncio
from utils.ssh_runner import run_command_on_server

async def start_container(server_id: str, container_name: str):
    return await run_command_on_server(server_id, f"docker start {container_name}", check=False, timeout=30)

async def stop_container(server_id: str, container_name: str):
    return await run_command_on_server(server_id, f"docker stop {container_name}", check=False, timeout=30)

async def restart_container(server_id: str, container_name: str):
    return await run_command_on_server(server_id, f"docker restart {container_name}", check=False, timeout=30)

async def update_pids_limit(server_id: str, container_name: str, limit: int):
    return await run_command_on_server(server_id, f"docker update --pids-limit {limit} {container_name}", check=False)

async def stop_all_rew_containers(server_id: str) -> list[str]:
    """
    Останавливает все контейнеры, начинающиеся на 'cat-'.
    Возвращает список имен остановленных контейнеров.
    """
    
    cmd_list = "docker ps -q --filter 'name=cat-'"
    res_list = await run_command_on_server(server_id, cmd_list, check=False)
    
    if res_list.exit_status != 0 or not res_list.stdout.strip():
        return []

    ids = res_list.stdout.strip().replace('\n', ' ')

    cmd_stop = f"docker stop {ids}"
    await run_command_on_server(server_id, cmd_stop, check=False, timeout=120)

    cmd_names = f"docker inspect --format='{{{{.Name}}}}' {ids}"
    res_names = await run_command_on_server(server_id, cmd_names, check=False)
    
    names = [n.strip().lstrip('/') for n in res_names.stdout.splitlines() if n.strip()]
    return names

async def temporary_cpu_boost(server_id: str, container_name: str, duration: int = 10, default_limit: float = 0.2):
    """
    Временно выдает 2 ядра процессора, затем возвращает лимит.
    """
    try:
        
        await run_command_on_server(server_id, f"docker update --cpus=\"2.0\" {container_name}", check=False)
        
        await asyncio.sleep(duration)

        await run_command_on_server(server_id, f"docker update --cpus=\"{default_limit}\" {container_name}", check=False)
    except Exception:
        pass
