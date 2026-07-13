import pytest
import asyncio
from roles import UserRole
import database as db
from config import ALL_ADMIN_IDS

@pytest.mark.asyncio
async def test_get_user_role():
    test_user_id = 123456789
    test_username = "testuser"
    test_first_name = "Test"

    await db.add_user(
        user_id=test_user_id, 
        username=test_username, 
        first_name=test_first_name
    )

    user_role = await db.get_user_role(test_user_id)

    assert user_role == UserRole.PARTICIPANT

    await db.set_user_role(test_user_id, UserRole.ADMIN.name)
    updated_role = await db.get_user_role(test_user_id)
    assert updated_role == UserRole.ADMIN

@pytest.mark.asyncio
async def test_promo_code_logic():
    creator_id = 9001
    activator_id = 9002
    await db.add_user(creator_id, "creator", "Creator")
    await db.add_user(activator_id, "activator", "Activator")

    await db.admin_update_user_balance(creator_id, 1000)

    promo_amount = 150.0
    promo_code = await db.create_promo_code(creator_id, promo_amount)

    assert promo_code is not None  
    assert promo_code.startswith("REWH-") 

    creator_balance = await db.get_user_balance(creator_id)
    assert creator_balance == 1000 - promo_amount

    status, amount = await db.activate_promo_code(activator_id, promo_code)
    assert status == 'success'
    assert amount == promo_amount

    activator_balance = await db.get_user_balance(activator_id)
    assert activator_balance == promo_amount

    status, amount = await db.activate_promo_code(activator_id, promo_code)
    assert status == 'already_activated'
    assert amount is None

@pytest.mark.asyncio
async def test_warning_system():
    user_id = 112233
    await db.add_user(user_id, "warner", "Warner")

    warn_count = await db.get_user_warn_count(user_id)
    assert warn_count == 0

    new_count = await db.add_user_warn(user_id)
    assert new_count == 1

    new_count = await db.add_user_warn(user_id)
    assert new_count == 2

    new_count = await db.remove_user_warn(user_id)
    assert new_count == 1

    await db.remove_user_warn(user_id) 
    new_count = await db.remove_user_warn(user_id) 
    assert new_count == 0
