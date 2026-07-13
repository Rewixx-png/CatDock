import asyncio
from datetime import datetime, timedelta
from config import TARIFFS
import database as db
import settings

def _parse_reg_date(reg_date_val) -> datetime:
    if not reg_date_val:
        return datetime.now() - timedelta(days=2)

    if isinstance(reg_date_val, datetime):
        return reg_date_val.replace(tzinfo=None)

    if isinstance(reg_date_val, str):
        reg_date_str = reg_date_val
        if '+' in reg_date_str:
            reg_date_str = reg_date_str.split('+')[0]
        if '.' in reg_date_str:
            reg_date_str = reg_date_str.split('.')[0]

        try:
            return datetime.strptime(reg_date_str, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            pass

    return datetime.now() - timedelta(days=2)

async def calculate_final_price(tariff_id: str, server_id: str, user_profile: dict) -> float:
    tariff = TARIFFS.get(tariff_id)
    if not tariff:
        return 0.0

    has_free_promo = user_profile.get('has_free_container_promo', 0)

    if has_free_promo and tariff_id == 'basic':
        return 0.0

    price = tariff['price_rub']
    if price <= 0:
        return 0.0

    surcharge = 0
    price_with_surcharge = price + surcharge

    reg_date = _parse_reg_date(user_profile.get('reg_date'))

    is_new_user = (datetime.now() - reg_date) < timedelta(days=1)

    active_discount = user_profile.get('active_discount_percent', 0)

    user_level = user_profile.get('level', 1)
    level_discount = min(user_level * settings.LEVEL_DISCOUNT_PER_LEVEL, settings.LEVEL_MAX_DISCOUNT)

    total_discount = min(active_discount + level_discount, settings.LEVEL_MAX_DISCOUNT)

    if is_new_user and TARIFFS[tariff_id]['price_rub'] > 0:
        has_containers = await db.get_user_containers(user_profile['user_id'])
        if not has_containers:
            
            total_discount = max(total_discount, 10)

    final_price = price_with_surcharge
    if total_discount > 0:
        final_price = price_with_surcharge * (1 - total_discount / 100)

    if final_price < 1.0 and final_price > 0.0:
        final_price = 1.0

    return max(0.0, final_price) 

async def use_purchase_bonus(user_id: int, tariff_id: str) -> tuple[str, str | None]:
    user_profile = await db.get_user_profile(user_id)
    if not user_profile:
        return tariff_id, None

    if user_profile.get('has_free_container_promo', 0) and tariff_id == 'basic':
        await db.set_user_free_container_promo(user_id, False, None)
        return 'free', 'free_container'

    if user_profile.get('active_discount_percent', 0) > 0 and TARIFFS[tariff_id]['price_rub'] > 0:
        await db.set_user_tariff_discount(user_id, 0, None)
        return tariff_id, 'tariff_discount'

    reg_date = _parse_reg_date(user_profile.get('reg_date'))

    is_new_user = (datetime.now() - reg_date) < timedelta(days=1)
    if is_new_user and TARIFFS[tariff_id]['price_rub'] > 0:
        has_containers = await db.get_user_containers(user_id)
        if not has_containers:
            return tariff_id, 'new_user_discount'

    return tariff_id, None
