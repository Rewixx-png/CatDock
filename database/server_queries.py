import logging
import json
from .core import get_db

async def add_server(server_id: str, name: str, ip: str, ssh_user: str, password: str = None, 
                     check_port: int = 22, limits: dict = None, **kwargs):
    try:
        limits_json = json.dumps(limits if limits else {})
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO servers 
                (id, name, ip, ssh_user, password, check_port, limits, proxy_ip, key_path, key_pass, is_local, domain_script_path)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    ip = EXCLUDED.ip,
                    password = EXCLUDED.password,
                    limits = EXCLUDED.limits
            """, server_id, name, ip, ssh_user, password, check_port, limits_json,
            kwargs.get('proxy_ip'), kwargs.get('key_path'), kwargs.get('key_pass'), 
            kwargs.get('is_local', False), kwargs.get('domain_script_path'))
    except Exception as e:
        logging.error(f"Ошибка добавления сервера {server_id}: {e}")
        raise e

async def get_all_servers_from_db() -> dict:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM servers ORDER BY id")

            servers = {}
            for row in rows:
                data = dict(row)
                servers[data['id']] = {
                    'name': data['name'],
                    'ip': data['ip'],
                    'proxy_ip': data.get('proxy_ip') or data['ip'],
                    'user': data['ssh_user'],
                    'password': data.get('password'),
                    'key_path': data.get('key_path'),
                    'key_pass': data.get('key_pass'),
                    'check_port': data['check_port'],
                    'local': data['is_local'],
                    'active': data['is_active'],
                    'domain_script_path': data.get('domain_script_path'),
                    'limits': json.loads(data['limits']) if data['limits'] else {}
                }
            return servers
    except Exception as e:
        logging.error(f"Ошибка получения серверов из БД: {e}")
        return {}

async def update_server_status(server_id: str, is_active: bool):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute("UPDATE servers SET is_active = $1 WHERE id = $2", is_active, server_id)
    except Exception as e:
        logging.error(f"Ошибка обновления статуса сервера {server_id}: {e}")

async def update_server_field(server_id: str, field: str, value: any):
    allowed_fields = ['name', 'ip', 'ssh_user', 'password', 'check_port', 'proxy_ip']
    if field not in allowed_fields:
        raise ValueError(f"Field {field} is not allowed for update.")

    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            query = f"UPDATE servers SET {field} = $1 WHERE id = $2"
            await conn.execute(query, value, server_id)
    except Exception as e:
        logging.error(f"Ошибка обновления поля {field} сервера {server_id}: {e}")
        raise e

async def delete_server(server_id: str):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM servers WHERE id = $1", server_id)
    except Exception as e:
        logging.error(f"Ошибка удаления сервера {server_id}: {e}")
