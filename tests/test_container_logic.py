import pytest
import asyncio
import database as db

@pytest.mark.asyncio
async def test_container_creation_and_deletion():
    user_id = 1001
    await db.add_user(user_id, "container_user", "ContainerUser")

    await db.add_user_container(
        user_id=user_id,
        server_id='de-1',
        container_name='test-container-123',
        image_id='hikka',
        tariff_id='basic',
        external_port=15000,
        login_url='http://example.com'
    )

    user_containers = await db.get_user_containers(user_id)

    assert len(user_containers) == 1 

    container = user_containers[0]
    assert container['user_id'] == user_id
    assert container['container_name'] == 'test-container-123'
    assert container['tariff_id'] == 'basic'
    assert container['is_frozen'] is False

    container_id = container['id']

    await db.set_container_frozen_state(container_id, True)
    frozen_c = await db.get_container_by_id(container_id)
    assert frozen_c['is_frozen'] is True

    await db.delete_user_container(container_id)

    user_containers_after_delete = await db.get_user_containers(user_id)
    assert len(user_containers_after_delete) == 0 

@pytest.mark.asyncio
async def test_count_containers_on_server():
    user_id_1 = 2001
    user_id_2 = 2002
    await db.add_user(user_id_1, "user1", "User1")
    await db.add_user(user_id_2, "user2", "User2")

    await db.add_user_container(user_id_1, 'de-1', 'c1', 'hikka', 'basic', 1, 'url')
    await db.add_user_container(user_id_2, 'de-1', 'c2', 'hikka', 'basic', 2, 'url')
    await db.add_user_container(user_id_1, 'de-1', 'c3', 'heroku', 'medium', 3, 'url')
    await db.add_user_container(user_id_2, 'sto-1', 'c4', 'hikka', 'basic', 4, 'url')

    count_de1_basic = await db.count_containers_on_server('de-1', 'basic')
    assert count_de1_basic == 2

    count_de1_medium = await db.count_containers_on_server('de-1', 'medium')
    assert count_de1_medium == 1

    count_sto1_basic = await db.count_containers_on_server('sto-1', 'basic')
    assert count_sto1_basic == 1

    count_sto2_basic = await db.count_containers_on_server('sto-2', 'basic')
    assert count_sto2_basic == 0

@pytest.mark.asyncio
async def test_container_ownership_check():
    
    uid = 3001
    await db.add_user(uid, "owner", "Owner")
    await db.add_user_container(uid, 's1', 'c_own', 'img', 'tar', 80, 'url')
    
    c = await db.get_container_by_name('c_own')
    assert c['user_id'] == uid

    new_uid = 3002
    await db.add_user(new_uid, "new_owner", "NewOwner")
    
    await db.change_container_owner(c['id'], new_uid)
    
    c_updated = await db.get_container_by_id(c['id'])
    assert c_updated['user_id'] == new_uid
