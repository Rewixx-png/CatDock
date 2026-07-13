import asyncio
import logging
import re
import time
from .ssh_runner import run_command_on_server

async def check_server_status(host: str, port: int, timeout: int = 5) -> tuple[str, int]:
    """
    Проверяет доступность порта и возвращает статус + пинг в мс.
    """
    start_time = time.perf_counter()
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), 
            timeout=timeout
        )
        end_time = time.perf_counter()
        
        writer.close()
        await writer.wait_closed()
        
        ping_ms = int((end_time - start_time) * 1000)
        return 'online', ping_ms
    except Exception:
        return 'offline', 9999

async def check_node_internet(server_id: str) -> bool:
    """
    Проверяет выход в интернет с ноды (curl до google).
    """
    try:
        
        cmd = "curl -I -s -m 3 https://www.google.com | head -n 1"
        res = await run_command_on_server(server_id, cmd, check=False, timeout=5)
        return "200" in res.stdout or "301" in res.stdout or "302" in res.stdout
    except Exception:
        return False

async def get_server_available_ram_mb(server_id: str) -> int | None:
    command = "awk '/MemAvailable/ {printf(\"%.0f\", $2 / 1024)}' /proc/meminfo"
    try:
        result = await run_command_on_server(server_id, command, timeout=10)
        stdout = result.stdout.strip()
        if stdout.isdigit():
            return int(stdout)
        return None
    except Exception as e:
        logging.error(f"Ошибка RAM для {server_id}: {e}")
        return None

def _parse_proc_stat(line):
    parts = line.split()
    if not parts or parts[0] != 'cpu':
        return None
    values = [int(x) for x in parts[1:]]
    total = sum(values)
    idle = values[3] 
    return total, idle

async def get_server_full_stats(server_id: str) -> dict:
    docker_top_cmd = (
        "docker stats --no-stream --format \"{{.Name}} {{.CPUPerc}}\" | "
        "tr -d '%' | sort -rn -k2 | head -n 1 | "
        "awk '{print $1\" (\"$2\"%)\"}'"
    )

    command = (
        "grep '^cpu ' /proc/stat; "  
        "sleep 1; "
        "echo '___'; "               
        "grep '^cpu ' /proc/stat; "  
        "echo '___'; "
        "awk '/MemTotal/ {total=$2} /MemAvailable/ {available=$2} END {printf(\"%.0f\", (total-available)/total*100)}' /proc/meminfo; " 
        "echo '___'; "
        "df -h / | awk 'NR==2 {print $5}'; " 
        "echo '___'; "
        "uptime -p | sed 's/up //'; "        
        "echo '___'; "
        f"{docker_top_cmd}"                  
    )

    default_stats = {"cpu": "Н/Д", "ram": "Н/Д", "disk": "Н/Д", "uptime": "Н/Д", "top_load": "—"}

    try:
        result = await run_command_on_server(server_id, command, timeout=30)

        if result.exit_status != 0:
            return default_stats

        output = result.stdout.strip()
        parts = output.split('___')

        if len(parts) < 6:
            return default_stats

        stats = default_stats.copy()

        stat1 = _parse_proc_stat(parts[0].strip())
        stat2 = _parse_proc_stat(parts[1].strip())

        if stat1 and stat2:
            total1, idle1 = stat1
            total2, idle2 = stat2
            diff_total = total2 - total1
            diff_idle = idle2 - idle1

            if diff_total > 0:
                cpu_usage = (1 - (diff_idle / diff_total)) * 100
                stats["cpu"] = f"{cpu_usage:.1f}%"
            else:
                stats["cpu"] = "0.0%"

        stats["ram"] = parts[2].strip() + "%"
        stats["disk"] = parts[3].strip()
        stats["uptime"] = parts[4].strip()

        docker_top = parts[5].strip()
        stats["top_load"] = docker_top if docker_top else "No Containers"

        if not stats["ram"].replace("%", "").isdigit(): stats["ram"] = "Н/Д"

        return stats

    except Exception as e:
        logging.error(f"Ошибка получения статов для {server_id}: {e}")
        return default_stats

async def get_server_ram_usage(server_id: str) -> int | None:
    stats = await get_server_full_stats(server_id)
    ram_str = stats['ram'].replace('%', '')
    if ram_str.isdigit():
        return int(ram_str)
    return None
