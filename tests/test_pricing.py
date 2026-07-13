import pytest
from datetime import datetime, timedelta
from utils.pricing import calculate_final_price
from config import TARIFFS

@pytest.mark.asyncio
async def test_pricing_basic_no_discounts():

    user_profile = {
        'user_id': 1,
        'reg_date': '2024-01-01 00:00:00',
        'active_discount_percent': 0,
        'level': 1 
    }

    price = await calculate_final_price('basic', 'de-1', user_profile)
    
    assert 34.0 < price < 35.0

@pytest.mark.asyncio
async def test_pricing_new_user_discount(mocker):

    now = datetime.now()
    recent_date = now.strftime('%Y-%m-%d %H:%M:%S')

    user_profile = {
        'user_id': 2,
        'reg_date': recent_date,
        'active_discount_percent': 0,
        'level': 1 
    }

    mocker.patch('database.get_user_containers', return_value=[])

    price = await calculate_final_price('medium', 'de-1', user_profile)

    base_price = 65.0

    expected = base_price * (1 - 0.10) 

    assert abs(price - expected) < 0.1

@pytest.mark.asyncio
async def test_pricing_personal_discount():
    
    user_profile = {
        'user_id': 3,
        'reg_date': '2024-01-01',
        'active_discount_percent': 50,
        'level': 10 
    }

    base_price = 125.0 
    expected = base_price * (1 - 0.55)

    price = await calculate_final_price('large', 'de-1', user_profile)
    assert abs(price - expected) < 0.1

@pytest.mark.asyncio
async def test_pricing_free_promo():
    
    user_profile = {
        'user_id': 4,
        'reg_date': '2024-01-01',
        'has_free_container_promo': True,
        'level': 1
    }

    price = await calculate_final_price('basic', 'de-1', user_profile)
    assert price == 0.0

    price_medium = await calculate_final_price('medium', 'de-1', user_profile)
    assert price_medium > 0.0
