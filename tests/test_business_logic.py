import pytest
import asyncio
import database as db
import time

@pytest.mark.asyncio
async def test_free_container_promo_duration():
    user_id = 3001
    await db.add_user(user_id, "promo_tester", "PromoTester")

    await db.set_user_free_container_promo(user_id, True, "TESTPROMO")

    await db.add_user_container(
        user_id=user_id,
        server_id='sto-1',
        container_name='free-promo-container',
        image_id='hikka',
        tariff_id='free', 
        external_port=20000,
        login_url='http://promo.test'
    )

    containers = await db.get_user_containers(user_id)

    assert len(containers) == 1
    free_container = containers[0]

    remaining_seconds = free_container['remaining_seconds']

    expected_duration_seconds = 2 * 24 * 60 * 60

    assert expected_duration_seconds - 60 < remaining_seconds < expected_duration_seconds + 60

@pytest.mark.asyncio
async def test_free_promo_user_flow_gives_correct_duration():
    user_id = 4001
    await db.add_user(user_id, "promo_flow_tester", "PromoFlow")

    await db.set_user_free_container_promo(user_id, True, "TESTPROMO")

    user_choice_data = {
        'server_id': 'sto-1',
        'tariff_id': 'basic', 
        'image_id': 'hikka'
    }

    user_profile = await db.get_user_profile(user_id)
    has_free_promo = user_profile.get('has_free_container_promo', 0)

    tariff_id_from_user = user_choice_data['tariff_id']
    tariff_id_for_db = tariff_id_from_user

    if has_free_promo and tariff_id_from_user == 'basic':
        tariff_id_for_db = 'free'

    await db.add_user_container(
        user_id=user_id,
        server_id=user_choice_data['server_id'],
        container_name='promo-flow-container',
        image_id=user_choice_data['image_id'],
        tariff_id=tariff_id_for_db, 
        external_port=20001,
        login_url='http://promo-flow.test'
    )

    containers = await db.get_user_containers(user_id)
    assert len(containers) == 1

    created_container = containers[0]
    remaining_seconds = created_container['remaining_seconds']

    expected_duration_seconds = 2 * 24 * 60 * 60

    assert expected_duration_seconds - 60 < remaining_seconds < expected_duration_seconds + 60

@pytest.mark.asyncio
async def test_advanced_referral_purchase():
    user_id = 5001
    price = 75.0
    initial_balance = 100.0
    await db.add_user(user_id, "ref_buyer", "RefBuyer")
    await db.update_user_balance(user_id, initial_balance)

    await db.update_user_balance(user_id, -price)
    await db.set_advanced_referral(user_id)

    user_profile = await db.get_user_profile(user_id)
    assert user_profile['balance'] == initial_balance - price
    assert user_profile['has_advanced_referral'] == 1

@pytest.mark.asyncio
async def test_expiring_container_notification_logic():
    user_id = 6001
    await db.add_user(user_id, "expiring_user", "ExpiringUser")

    await db.add_user_container(user_id, 'de-1', 'c1', 'h', 'b', 1, 'url')
    await db.add_user_container(user_id, 'de-1', 'c2', 'h', 'b', 2, 'url')
    await db.add_user_container(user_id, 'de-1', 'c3', 'h', 'b', 3, 'url')

    containers = await db.get_user_containers(user_id)
    c1_id, c2_id, c3_id = containers[0]['id'], containers[1]['id'], containers[2]['id']

    await db.admin_set_container_time(c1_id, 3) 
    await db.admin_set_container_time(c2_id, 10) 
    await db.admin_set_container_time(c3_id, 1) 

    expiring_containers = await db.get_expiring_containers([1, 3])

    assert len(expiring_containers) == 2 

    expiring_ids = {c['id'] for c in expiring_containers}
    assert c1_id in expiring_ids 
    assert c3_id in expiring_ids 
    assert c2_id not in expiring_ids
