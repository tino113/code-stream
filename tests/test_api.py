from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def test_health():
    res = client.get('/health')
    assert res.status_code == 200
    assert res.json()['status'] == 'ok'


def test_register_login_and_execute():
    reg = client.post('/api/auth/register', json={
        'email': 'teacher@example.com',
        'password': 'password123',
        'role': 'teacher',
    })
    assert reg.status_code in (200, 409)

    login = client.post('/api/auth/login', json={
        'email': 'teacher@example.com',
        'password': 'password123',
    })
    assert login.status_code == 200
    data = login.json()
    assert data['token_type'] == 'bearer'

    execute = client.post('/api/execute', json={'code': 'print(1+1)'})
    assert execute.status_code == 200
    assert execute.json()['stdout'].strip() == '2'


def test_debug_agent_policy():
    res = client.post('/api/debug', json={
        'code': 'x=1',
        'error_message': 'NameError: name y is not defined'
    })
    assert res.status_code == 200
    payload = res.json()
    assert payload['policy'] == 'no_code_output'
    assert 'def ' not in payload['guidance']
