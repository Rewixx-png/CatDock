import logging
from utils.ssh_runner import run_command_on_server

async def list_files_in_container(server_id: str, container_name: str, path: str) -> list:
    """Возвращает список .py файлов в папке."""
    try:
        
        cmd = f"docker exec {container_name} ls -1 {path}"
        result = await run_command_on_server(server_id, cmd, check=False)
        
        if result.exit_status != 0:
            if "No such file" in result.stderr:
                return [] 
            raise Exception(f"ls failed: {result.stderr}")

        files = []
        for line in result.stdout.strip().splitlines():
            line = line.strip()
            if line.endswith(".py"):
                files.append(line)
        return files

    except Exception as e:
        logging.error(f"FS List Error on {server_id}: {e}")
        return []

async def read_file_from_container(server_id: str, container_name: str, full_path: str) -> bytes | None:
    """Читает содержимое файла (cat)"""
    try:
        
        cmd = f"docker exec {container_name} cat {full_path}"
        result = await run_command_on_server(server_id, cmd, check=False)
        
        if result.exit_status != 0:
            return None
            
        return result.stdout.encode('utf-8') 
    except Exception as e:
        logging.error(f"FS Read Error on {server_id}: {e}")
        return None
