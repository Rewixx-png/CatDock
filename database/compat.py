"""No-op database API for features intentionally removed from CatDock.

The old RewHost web API and a few background helpers still import these names.
Keeping shape-compatible async stubs prevents late ``AttributeError`` failures
without reviving promo, game, cosmetics, leveling, module or backup tables.
"""

from typing import Any


# Promo compatibility -------------------------------------------------------

async def create_promo_code(*args: Any, **kwargs: Any) -> None:
    return None


async def create_promo_code_safe(*args: Any, **kwargs: Any) -> None:
    return None


async def activate_promo_code(*args: Any, **kwargs: Any) -> tuple[str, None]:
    return "not_found", None


async def create_global_promo_code(*args: Any, **kwargs: Any) -> None:
    return None


async def find_and_deactivate_global_promo(*args: Any, **kwargs: Any) -> None:
    return None


# Games and leveling compatibility -----------------------------------------

async def add_game_history_record(*args: Any, **kwargs: Any) -> None:
    return None


async def get_user_game_history(*args: Any, **kwargs: Any) -> list:
    return []


async def add_user_xp(*args: Any, **kwargs: Any) -> tuple[int, int, bool]:
    return 1, 0, False


# Cosmetics compatibility --------------------------------------------------

async def set_container_icon(*args: Any, **kwargs: Any) -> bool:
    return False


# Saved modules compatibility ----------------------------------------------

async def add_user_module(*args: Any, **kwargs: Any) -> None:
    return None


async def get_user_saved_modules(*args: Any, **kwargs: Any) -> list:
    return []


async def get_module_by_id(*args: Any, **kwargs: Any) -> None:
    return None


async def delete_user_module(*args: Any, **kwargs: Any) -> bool:
    return False


# Full backup compatibility ------------------------------------------------

async def save_backup_record(*args: Any, **kwargs: Any) -> None:
    return None


async def get_user_backup(*args: Any, **kwargs: Any) -> None:
    return None


async def delete_backup_record(*args: Any, **kwargs: Any) -> bool:
    return False
