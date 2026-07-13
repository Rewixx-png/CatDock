import json
import re
import logging
from utils.ssh_runner import run_command_on_server
from utils.cache import cache_get, cache_set

async def get_container_status(server_id: str, container_name: str) -> str:
    
    cache_key = f"status:{server_id}:{container_name}"
    cached_status = await cache_get(cache_key)
    
    if cached_status:
        return cached_status

    try:
        result = await run_command_on_server(server_id, f'docker ps -a --filter "name=^{container_name}$" --format "{{{{.State}}}}"')
        status = result.stdout.strip()
        final_status = 'stopped' if status.startswith('exited') else (status or 'not_found')

        await cache_set(cache_key, final_status, ttl=10)
        return final_status
    except Exception:
        return 'not_found'

async def get_session_status(server_id: str, container_name: str, image_id: str) -> str:
    
    cache_key = f"session_status:{server_id}:{container_name}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    try:
        result = await run_command_on_server(server_id, f'docker exec {container_name} find / -name "*.session" -type f', check=False)
        status = 'active' if result.exit_status == 0 and result.stdout.strip() else 'not_found'
        
        await cache_set(cache_key, status, ttl=30)
        return status
    except Exception:
        return 'error'

async def check_session_files_exist(server_id: str, container_name: str) -> bool:
    try:
        cmd = f"docker exec {container_name} find /data -type f \\( -name '*.session' -o -name 'session.string' \\) | head -n 1"
        result = await run_command_on_server(server_id, cmd, check=False, timeout=10)

        if result.exit_status == 0 and result.stdout.strip():
            return True
        return False
    except Exception as e:
        logging.error(f"Ошибка проверки сессии в {container_name} на {server_id}: {e}")
        return False

async def get_container_stats(server_id: str, container_name: str) -> dict | None:
    
    cache_key = f"stats:{server_id}:{container_name}"
    cached_json = await cache_get(cache_key)
    if cached_json:
        try:
            return json.loads(cached_json)
        except: pass

    try:
        result = await run_command_on_server(server_id, f'docker stats --no-stream --format "{{{{json .}}}}" {container_name}', check=False)
        if result.exit_status != 0 or not result.stdout.strip(): return None
        stats_raw = json.loads(result.stdout.strip())

        cpu_str = stats_raw.get('CPUPerc', '0').replace('%', '')
        mem_str = stats_raw.get('MemUsage', '0').split('/')[0].strip()

        cpu_usage = float(cpu_str)
        
        mem_val_match = re.search(r'(\d+\.?\d*)', mem_str)
        mem_usage = float(mem_val_match.group(1)) if mem_val_match else 0.0
        
        if 'GiB' in mem_str: mem_usage *= 1024
        elif 'KiB' in mem_str: mem_usage /= 1024

        final_stats = {
            'cpu_usage': round(cpu_usage, 2), 
            'memory_usage_mb': round(mem_usage, 2), 
            'cpu_raw': stats_raw.get('CPUPerc'), 
            'ram_raw': stats_raw.get('MemUsage')
        }
        
        await cache_set(cache_key, json.dumps(final_stats), ttl=5)
        return final_stats
    except Exception:
        return None

async def get_container_disk_usage(server_id: str, container_name: str) -> str:
    
    cache_key = f"disk:{server_id}:{container_name}"
    cached = await cache_get(cache_key)
    if cached: return cached

    try:
        res = await run_command_on_server(server_id, f'docker ps -s --filter "name=^{container_name}$" --format "{{{{.Size}}}}"')
        val = res.stdout.strip() or 'N/A'
        await cache_set(cache_key, val, ttl=60)
        return val
    except Exception: return 'N/A'

async def get_container_logs(server_id: str, container_name: str, lines: int) -> str | None:
    
    try:
        res = await run_command_on_server(server_id, f'docker logs --tail {lines} {container_name}', check=False)
        return res.stdout + res.stderr
    except Exception: return None

async def get_all_containers_pids(server_id: str) -> dict[str, int]:
    try:
        result = await run_command_on_server(server_id, "docker stats --no-stream --format '{{.Name}}:{{.PIDs}}'", check=False, timeout=15)
        pids_map = {}
        if result.exit_status == 0 and result.stdout:
            for line in result.stdout.strip().splitlines():
                parts = line.split(':')
                if len(parts) == 2:
                    name, pids = parts[0], parts[1]
                    if pids.isdigit():
                        pids_map[name] = int(pids)
        return pids_map
    except Exception as e:
        logging.error(f"Ошибка получения PIDs с сервера {server_id}: {e}")
        return {}
