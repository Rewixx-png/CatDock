import logging
from typing import Set
from .core import get_db
from config import TARIFFS, DEFAULT_CPU_LIMIT

async def add_user_container(user_id: int, server_id: str, container_name: str, image_id: str, tariff_id: str, external_port: int, login_url: str):
    if tariff_id == 'admin':
        initial_seconds = 999999999
    elif tariff_id == 'free':
        initial_seconds = 2 * 24 * 60 * 60
    else:
        initial_seconds = 30 * 24 * 60 * 60

    try:
        ram_mb_val = int(TARIFFS.get(tariff_id, {}).get('ram_mb', 300))
        cpu_limit_val = float(DEFAULT_CPU_LIMIT)
        external_port_val = int(external_port)
    except (ValueError, TypeError):
        logging.error(f"Ошибка типов данных при добавлении контейнера: port={external_port}, tariff={tariff_id}")
        raise ValueError("Invalid data types for container insertion")

    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO user_containers 
                   (user_id, server_id, container_name, image_id, tariff_id, external_port, remaining_seconds, is_frozen, login_url, cpu_limit, ram_mb, is_login_pending, is_blocked, is_web_loading) 
                   VALUES ($1, $2, $3, $4, $5, $6, $7, FALSE, $8, $9, $10, FALSE, FALSE, TRUE)""",
                user_id, server_id, container_name, image_id, tariff_id, external_port_val, initial_seconds, login_url, cpu_limit_val, ram_mb_val
            )
    except Exception as e:
        logging.error(f"Ошибка при добавлении контейнера в БД: {e}", exc_info=True)
        raise e

async def get_user_containers(user_id: int) -> list:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM user_containers WHERE user_id = $1", user_id)
            return [dict(row) for row in rows]
    except Exception as e:
        logging.error(f"Ошибка при получении контейнеров пользователя {user_id}: {e}")
        return []

async def get_container_by_id(container_id: int) -> dict | None:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM user_containers WHERE id = $1", container_id)
            return dict(row) if row else None
    except Exception as e:
        logging.error(f"Ошибка при получении контейнера по ID {container_id}: {e}")
        return None

async def get_active_containers() -> list:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM user_containers WHERE is_frozen = FALSE AND remaining_seconds > 0")
            return [dict(row) for row in rows]
    except Exception as e:
        logging.error(f"Ошибка при получении активных контейнеров: {e}")
        return []

async def get_frozen_containers() -> list:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM user_containers WHERE is_frozen = TRUE")
            return [dict(row) for row in rows]
    except Exception as e:
        logging.error(f"Ошибка при получении замороженных контейнеров: {e}")
        return []

async def get_expiring_containers(days_left: list[int]) -> list:
    if not days_left:
        return []

    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            conditions = []
            params = []
            counter = 1
            for day in days_left:
                low = day * 86400 - 3600
                high = day * 86400 + 3600
                conditions.append(f"(remaining_seconds BETWEEN ${counter} AND ${counter+1})")
                params.extend([low, high])
                counter += 2

            full_query = "SELECT * FROM user_containers WHERE " + " OR ".join(conditions)
            rows = await conn.fetch(full_query, *params)
            return [dict(row) for row in rows]
    except Exception as e:
        logging.error(f"Ошибка при получении истекающих контейнеров: {e}")
        return []

async def update_containers_time(container_ids: list, seconds_to_decrement: int):
    if not container_ids: return
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE user_containers SET remaining_seconds = remaining_seconds - $1 WHERE id = ANY($2::int[])",
                seconds_to_decrement, container_ids
            )
    except Exception as e:
        logging.error(f"Ошибка при массовом обновлении времени контейнеров: {e}")

async def add_container_time(container_id: int, seconds_to_add: int):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE user_containers SET remaining_seconds = remaining_seconds + $1 WHERE id = $2",
                seconds_to_add, container_id
            )
    except Exception as e:
        logging.error(f"Ошибка при продлении подписки для контейнера {container_id}: {e}")

async def update_container_last_notification(container_id: int, days: int):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE user_containers SET last_notification_days = $1 WHERE id = $2",
                days, container_id
            )
    except Exception as e:
        logging.error(f"Ошибка при обновлении флага уведомления для контейнера {container_id}: {e}")

async def set_container_frozen_state(container_id: int, is_frozen: bool):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute("UPDATE user_containers SET is_frozen = $1 WHERE id = $2", is_frozen, container_id)
    except Exception as e:
        logging.error(f"Ошибка при установке статуса заморозки для {container_id}: {e}")

async def set_container_blocked_state(container_id: int, is_blocked: bool):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute("UPDATE user_containers SET is_blocked = $1 WHERE id = $2", is_blocked, container_id)
    except Exception as e:
        logging.error(f"Ошибка при установке статуса блокировки для {container_id}: {e}")

async def set_container_login_pending(container_id: int, is_pending: bool):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute("UPDATE user_containers SET is_login_pending = $1 WHERE id = $2", is_pending, container_id)
    except Exception as e:
        logging.error(f"Ошибка при установке флага login_pending для {container_id}: {e}")

async def set_container_web_loading(container_id: int, is_loading: bool):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute("UPDATE user_containers SET is_web_loading = $1 WHERE id = $2", is_loading, container_id)
    except Exception as e:
        logging.error(f"Ошибка при обновлении статуса загрузки веба для {container_id}: {e}")

async def get_containers_loading_web() -> list:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM user_containers WHERE is_web_loading = TRUE AND is_frozen = FALSE")
            return [dict(row) for row in rows]
    except Exception as e:
        logging.error(f"Ошибка получения загружающихся контейнеров: {e}")
        return []

async def get_all_containers_paginated(page: int, page_size: int = 30, sort_by: str = 'time', search_query: str | None = None) -> tuple[list, int]:
    total_count = 0
    offset = page * page_size

    tariff_ids = list(TARIFFS.keys())
    tariff_rams = [info.get('ram_mb', 0) for info in TARIFFS.values()]
    tariff_prices = [info.get('price_rub', 0) for info in TARIFFS.values()]

    valid_sort_options = {
        'ram': "tm.ram_mb DESC, uc.id DESC",
        'price': "tm.price_rub DESC, uc.id DESC",
        'time': "uc.remaining_seconds ASC, uc.id DESC"
    }
    order_clause = valid_sort_options.get(sort_by, valid_sort_options['time'])

    try:
        pool = await get_db()
        async with pool.acquire() as conn:

            params = [tariff_ids, tariff_rams, tariff_prices]
            
            tariff_cte = f"""
            WITH tariff_meta AS (
                SELECT * FROM unnest($1::text[], $2::int[], $3::float[]) AS t(id, ram_mb, price_rub)
            )
            """

            base_query = """
                SELECT uc.* FROM user_containers uc
                LEFT JOIN tariff_meta tm ON uc.tariff_id = tm.id
            """

            main_where = ""
            count_where = ""
            count_args = []

            if search_query:
                
                main_where = f" WHERE uc.container_name ILIKE $4 OR uc.user_id::text LIKE $4 OR uc.id::text LIKE $4"
                params.append(f"%{search_query}%")

                count_where = f" WHERE uc.container_name ILIKE $1 OR uc.user_id::text LIKE $1 OR uc.id::text LIKE $1"
                count_args = [f"%{search_query}%"]

            count_sql = f"SELECT COUNT(*) FROM user_containers uc {count_where}"
            total_count = await conn.fetchval(count_sql, *count_args)

            limit_idx = len(params) + 1
            offset_idx = len(params) + 2
            
            select_sql = f"{tariff_cte} {base_query}{main_where} ORDER BY {order_clause} LIMIT ${limit_idx} OFFSET ${offset_idx}"
            params.extend([page_size, offset])

            rows = await conn.fetch(select_sql, *params)
            return [dict(row) for row in rows], total_count

    except Exception as e:
        logging.error(f"Ошибка получения пагинированного списка контейнеров: {e}", exc_info=True)
        return [], 0

async def get_all_admin_containers() -> list:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM user_containers WHERE tariff_id = 'admin' ORDER BY id DESC")
            return [dict(row) for row in rows]
    except Exception as e:
        logging.error(f"Ошибка при получении админ-контейнеров: {e}")
        return []

async def delete_user_container(container_id: int):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM user_containers WHERE id = $1", container_id)
    except Exception as e:
        logging.error(f"Ошибка при удалении контейнера {container_id} из БД: {e}")

async def update_container_image(container_id: int, new_image_id: str):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute("UPDATE user_containers SET image_id = $1 WHERE id = $2", new_image_id, container_id)
    except Exception as e:
        logging.error(f"Ошибка при смене образа для контейнера {container_id}: {e}")

async def update_container_server(container_id: int, new_server_id: str, new_port: int, new_container_name: str, login_url: str):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE user_containers SET server_id = $1, external_port = $2, container_name = $3, login_url = $4 WHERE id = $5",
                new_server_id, new_port, new_container_name, login_url, container_id
            )
    except Exception as e:
        logging.error(f"Ошибка при смене сервера для контейнера {container_id}: {e}")

async def update_container_name(container_id: int, new_name: str):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute("UPDATE user_containers SET container_name = $1 WHERE id = $2", new_name, container_id)
    except Exception as e:
        logging.error(f"Ошибка при смене имени для контейнера {container_id}: {e}")

async def update_container_cpu_limit(container_id: int, new_limit: float):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute("UPDATE user_containers SET cpu_limit = $1 WHERE id = $2", new_limit, container_id)
    except Exception as e:
        logging.error(f"Ошибка при обновлении лимита CPU для контейнера {container_id}: {e}", exc_info=True)

async def update_container_ram(container_id: int, new_ram_mb: int):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute("UPDATE user_containers SET ram_mb = $1 WHERE id = $2", new_ram_mb, container_id)
    except Exception as e:
        logging.error(f"Ошибка при обновлении лимита RAM для контейнера {container_id}: {e}", exc_info=True)

async def count_containers_on_server(server_id: str, tariff_id: str) -> int:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            count = await conn.fetchval("SELECT COUNT(*) FROM user_containers WHERE server_id = $1 AND tariff_id = $2", server_id, tariff_id)
            return count or 0
    except Exception as e:
        logging.error(f"Ошибка при подсчете контейнеров для {server_id}/{tariff_id}: {e}")
        return 0

async def admin_update_container_time(container_id: int, days_to_add: int):
    seconds_to_add = days_to_add * 24 * 60 * 60
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE user_containers SET remaining_seconds = remaining_seconds + $1 WHERE id = $2",
                seconds_to_add, container_id
            )
    except Exception as e:
        logging.error(f"Ошибка админского обновления времени для контейнера {container_id}: {e}")

async def count_active_containers() -> int:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            count = await conn.fetchval("SELECT COUNT(id) FROM user_containers WHERE remaining_seconds > 0 AND is_frozen = FALSE")
            return count or 0
    except Exception as e:
        logging.error(f"Ошибка при подсчете активных контейнеров: {e}")
        return 0

async def admin_set_container_time(container_id: int, days: int):
    seconds_to_set = days * 24 * 60 * 60
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE user_containers SET remaining_seconds = $1 WHERE id = $2",
                seconds_to_set, container_id
            )
    except Exception as e:
        logging.error(f"Ошибка админской установки времени для контейнера {container_id}: {e}")

async def find_orphaned_containers(valid_server_ids: Set[str]) -> list:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            all_containers = await conn.fetch("SELECT id, user_id, server_id, container_name FROM user_containers")

        orphaned = [dict(c) for c in all_containers if c['server_id'] not in valid_server_ids]
        return orphaned

    except Exception as e:
        logging.error(f"Ошибка при получении всех контейнеров для поиска осиротевших: {e}")
        return []

async def change_container_owner(container_id: int, new_user_id: int):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute("UPDATE user_containers SET user_id = $1 WHERE id = $2", new_user_id, container_id)
        logging.info(f"Владелец контейнера {container_id} изменен на {new_user_id}.")
    except Exception as e:
        logging.error(f"Ошибка при смене владельца контейнера {container_id}: {e}", exc_info=True)

async def get_container_by_name(container_name: str) -> dict | None:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM user_containers WHERE container_name = $1", container_name)
            return dict(row) if row else None
    except Exception as e:
        logging.error(f"Ошибка при получении контейнера по имени {container_name}: {e}")
        return None

async def get_all_container_names() -> set:
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT container_name FROM user_containers")
            return {row['container_name'] for row in rows}
    except Exception as e:
        logging.error(f"Ошибка при получении всех имен контейнеров: {e}")
        return set()

async def set_container_icon(container_id: int, icon_emoji: str | None):
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE user_containers SET cosmetic_icon = $1 WHERE id = $2",
                icon_emoji, container_id
            )
    except Exception as e:
        logging.error(f"Ошибка при установке иконки для контейнера {container_id}: {e}")
