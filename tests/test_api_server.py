import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock
from api import setup_api_server
from roles import UserRole

@pytest.fixture
def client(mocker):
    mock_bot = MagicMock()
    app = setup_api_server(mock_bot)

    mocker.patch('database.get_user_by_web_token', side_effect=lambda token: 
        {'user_id': 8001, 'username': 'test_api', 'first_name': 'Tester'} if token == 'valid_token' else None
    )

    mocker.patch('database.get_user_profile', return_value={
        'user_id': 8001, 'username': 'test_api', 'first_name': 'Tester',
        'balance': 100.0, 'ref_balance': 0.0, 'role_enum': 0, 'role': 'PARTICIPANT',
        'level': 1, 'xp': 0, 'reg_date': '2025-01-01', 'is_blocked': False, 'effective_role': 0
    })
    mocker.patch('database.get_user_role', return_value=UserRole.PARTICIPANT)
    mocker.patch('database.get_user_containers', return_value=[
        {'id': 1, 'container_name': 'test-cont', 'server_id': 'de-1', 'tariff_id': 'basic', 'image_id': 'hikka', 'remaining_seconds': 1000}
    ])
    mocker.patch('database.get_referral_stats', return_value={'count': 0, 'referrer_name': None})
    mocker.patch('database.count_unread_notifications', return_value=0)
    mocker.patch('database.get_user_tickets', return_value=[])
    mocker.patch('database.get_user_settings', return_value={})
    mocker.patch('database.get_user_custom_avatar', return_value=None)

    mocker.patch('database.get_container_by_id', return_value={
        'id': 1, 'user_id': 8001, 'container_name': 'test-cont', 
        'server_id': 'de-1', 'tariff_id': 'basic', 'image_id': 'hikka',
        'external_port': 20000, 'login_url': 'http://test', 'remaining_seconds': 1000,
        'is_frozen': False, 'status': 'running'
    })

    mocker.patch('utils.docker.get_container_status', return_value='running')
    mocker.patch('utils.docker.get_container_stats', return_value={'cpu_usage': 1.5, 'ram_raw': '100M'})
    mocker.patch('utils.docker.get_container_disk_usage', return_value='500M')
    mocker.patch('utils.docker.allocator.find_optimal_server', return_value='de-1')

    return TestClient(app)

def test_ping_endpoint(client):

    resp = client.get('/api/v1/public/server_status') 
    assert resp.status_code == 200
    data = resp.json()
    assert data['status'] in ['success', 'pending']

def test_root_endpoint(client):
    resp = client.get('/')
    assert resp.status_code == 200
    assert 'text/html' in resp.headers['content-type']

def test_dashboard_access(client):
    
    resp = client.get('/api/v1/user/dashboard')
    assert resp.status_code == 403

    resp = client.get('/api/v1/user/dashboard', headers={'X-Web-Access-Token': 'invalid'})
    assert resp.status_code == 403

    resp = client.get('/api/v1/user/dashboard', headers={'X-Web-Access-Token': 'valid_token'})
    assert resp.status_code == 200
    data = resp.json()
    assert data['status'] == 'success'
    assert data['data']['profile']['username'] == 'test_api'
    
    assert len(data['data']['containers']) == 1

def test_container_list(client):
    resp = client.get('/api/v1/user/containers', headers={'X-Web-Access-Token': 'valid_token'})
    assert resp.status_code == 200
    data = resp.json()
    
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]['container_name'] == 'test-cont'

def test_container_details(client):
    resp = client.get('/api/v1/user/container/1', headers={'X-Web-Access-Token': 'valid_token'})
    assert resp.status_code == 200
    data = resp.json()
    assert data['data']['container_name'] == 'test-cont'
