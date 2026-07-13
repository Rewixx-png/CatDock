import asyncio
import asyncssh
import logging
from utils import bot_state 

logging.getLogger("asyncssh").setLevel(logging.WARNING)

async def _get_ssh_connection(server_id: str) -> asyncssh.SSHClientConnection:
    is_active = bot_state.server_states.get(server_id, True)
    if not is_active:
        raise ConnectionError(f"Server {server_id} is disabled in bot_state (Skip SSH).")

    server_config = bot_state.servers_cache.get(server_id)

    if not server_config:
        from utils.server_loader import load_servers_to_cache
        if not bot_state.servers_cache:
            await load_servers_to_cache()
            server_config = bot_state.servers_cache.get(server_id)

    if not server_config:
        raise ValueError(f"❌ Server '{server_id}' not found in cache or DB.")

    ip = server_config['ip']
    port = server_config.get('check_port', 22)
    user = server_config['user']

    connect_options = {
        'host': ip,
        'port': port,
        'username': user,
        'known_hosts': None,
        'connect_timeout': 15,
        'server_host_key_algs': '+ssh-rsa,ssh-dss',
        'encryption_algs': '+aes128-cbc,3des-cbc',
        'kex_algs': '+diffie-hellman-group1-sha1',
    }

    if server_config.get('key_path'):
        connect_options['client_keys'] = [server_config['key_path']]
        if server_config.get('key_pass'):
            connect_options['passphrase'] = server_config['key_pass']
    elif server_config.get('password'):
        connect_options['password'] = server_config['password']
    else:
        raise ValueError(f"❌ For server {server_id} ({ip}) auth method is missing (no pass/key).")

    last_error = None

    for attempt in range(1, 4):
        try:
            conn = await asyncssh.connect(**connect_options)
            return conn
        except asyncssh.PermissionDenied as e:
            logging.error(f"[SSH] Auth Failed for {server_id} ({ip}): {e}")
            raise e 
        except (asyncssh.DisconnectError, OSError, asyncio.TimeoutError) as e:
            last_error = e
            logging.warning(f"[SSH] Fail {server_id} ({ip}) Attempt {attempt}: {type(e).__name__} - {e}")
            await asyncio.sleep(2)
        except Exception as e:
            logging.error(f"[SSH] Critical Fail {server_id}: {e}", exc_info=True)
            raise e

    error_msg = f"SSH Connect Failed to {server_id} ({ip}) after 3 attempts: {type(last_error).__name__} - {last_error}"
    raise ConnectionError(error_msg)

async def run_command_on_server(server_id: str, command: str, check: bool = True, timeout: int = 20) -> asyncssh.SSHCompletedProcess | object:
    if not bot_state.server_states.get(server_id, True):
        class FakeResult:
            def __init__(self):
                self.exit_status = -1
                self.stdout = ""
                self.stderr = f"Server {server_id} is disabled."
        return FakeResult()

    server_config = bot_state.servers_cache.get(server_id)

    if server_config and server_config.get('local'):
        try:
            proc = await asyncio.create_subprocess_shell(
                command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                raise TimeoutError(f"Local command timed out: {command}")

            class LocalProcess:
                def __init__(self, p, so, se):
                    self.exit_status = p.returncode
                    self.stdout = so.decode('utf-8', errors='ignore')
                    self.stderr = se.decode('utf-8', errors='ignore')

            result = LocalProcess(proc, stdout, stderr)

            if check and result.exit_status != 0:
                raise Exception(f"Local CMD Error (Exit {result.exit_status}): {result.stderr.strip()}")

            return result
        except Exception as e:
            logging.error(f"[LOCAL CMD] Failed: {e}")
            raise e

    try:
        async with await _get_ssh_connection(server_id) as conn:
            return await conn.run(command, check=check, timeout=timeout)
    except Exception as e:
        raise e

async def create_interactive_process(server_id: str, command: str) -> asyncssh.SSHClientProcess | None:
    if not bot_state.server_states.get(server_id, True):
        return None

    try:
        conn = await _get_ssh_connection(server_id)
        process = await conn.create_process(command, term_type='xterm-color')
        return process
    except Exception as e:
        logging.error(f"Interactive Process Error on {server_id}: {e}")
        return None
