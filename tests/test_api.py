from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def test_health():
    res = client.get('/health')
    assert res.status_code == 200
    assert res.json()['status'] == 'ok'
    assert res.json()['phase'] == 3
    assert res.json()['ui'] == 'bootstrap+monaco'


def test_pages_render():
    assert client.get('/').status_code == 200
    assert client.get('/login').status_code == 200
    assert client.get('/teacher').status_code == 200
    assert client.get('/student').status_code == 200


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


def test_phase3_recording_render_and_voiceover_endpoints():
    create = client.post('/api/recordings', json={
        'title': 'Lesson 3',
        'created_by': 'teacher@example.com',
        'events': [
            {'t': 0, 'type': 'recording_start'},
            {'t': 1240, 'type': 'edit'},
            {'t': 2310, 'type': 'run', 'file': 'main.py'},
            {'t': 3000, 'type': 'file_switch', 'file': 'helpers.py'},
            {'t': 4100, 'type': 'annotation', 'file': 'helpers.py'},
        ],
        'annotations': [{'t': 1300, 'text': 'Introduce loop'}],
    })
    assert create.status_code == 200
    recording_id = create.json()['id']

    suggestions_res = client.get(f'/api/recordings/{recording_id}/suggest-annotations')
    assert suggestions_res.status_code == 200
    assert len(suggestions_res.json()['suggestions']) >= 1

    render_res = client.post('/api/render-jobs', json={'recording_id': recording_id, 'format': 'mp4'})
    assert render_res.status_code == 200
    assert render_res.json()['status'] == 'completed'
    job_id = render_res.json()['job_id']

    render_get = client.get(f'/api/render-jobs/{job_id}')
    assert render_get.status_code == 200
    assert render_get.json()['recording_id'] == recording_id

    tts_res = client.post('/api/voiceover/tts', json={'text': 'Intro and walkthrough', 'voice': 'alloy'})
    assert tts_res.status_code == 200
    assert tts_res.json()['audio_url'].endswith('.mp3')

    sync_res = client.post('/api/voiceover/auto-sync', json={
        'recording_id': recording_id,
        'transcript_chunks': [{'text': 'Intro section'}, {'text': 'Refactor section'}],
    })
    assert sync_res.status_code == 200
    assert len(sync_res.json()['segments']) == 2
