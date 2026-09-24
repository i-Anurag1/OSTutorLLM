import os, uuid, io
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def login(email, password):
    r = client.post('/api/auth/login', json={'email': email, 'password': password})
    assert r.status_code == 200, r.text
    return r.json()['access_token']


def auth(token):
    return {'Authorization': f'Bearer {token}'}


def test_full_system_end_to_end():
    # Infrastructure + public API
    r = client.get('/health')
    assert r.status_code == 200, r.text
    assert r.json()['status'] == 'ok'

    # Seeded role accounts
    student = login('student@ostutor.local', 'Student123!')
    faculty = login('faculty@ostutor.local', 'Faculty123!')
    admin = login('admin@ostutor.local', 'Admin123!')

    # Auth / dashboard / profile / topics
    r = client.get('/api/auth/me', headers=auth(student)); assert r.status_code == 200
    r = client.get('/api/dashboard', headers=auth(student)); assert r.status_code == 200
    r = client.get('/api/topics'); assert r.status_code == 200 and len(r.json()) >= 17
    r = client.put('/api/profile', headers=auth(student), json={'name': 'Student Test'}); assert r.status_code == 200

    # Student RBAC denial
    assert client.get('/api/sources', headers=auth(student)).status_code == 403
    assert client.get('/api/admin/analytics', headers=auth(student)).status_code == 403
    assert client.get('/api/admin/students', headers=auth(student)).status_code == 403

    # Grounded tutor
    r = client.post('/api/tutor/chat', headers=auth(student), json={
        'message': 'Explain page replacement and compare FIFO LRU and Optimal.',
        'topic': 'Paging', 'difficulty': 'medium', 'mode': 'teach'
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get('answer') and body.get('retrieved', 0) > 0 and body.get('citations')

    # Progress, including fresh NULL-safe path
    r = client.post('/api/progress', headers=auth(student), json={'topic': 'Paging', 'score': 100, 'activity': 'test'}); assert r.status_code == 200, r.text
    r = client.get('/api/dashboard', headers=auth(student)); assert r.status_code == 200

    # Simulators
    sim_cases = [
        ('/api/simulators/cpu', {'algorithm':'Round Robin','quantum':2,'processes':[{'pid':'P1','arrival':0,'burst':5,'priority':2},{'pid':'P2','arrival':1,'burst':3,'priority':1}]}),
        ('/api/simulators/page-replacement', {'algorithm':'LRU','reference_string':[1,2,1,3,4,1],'frames':3}),
        ('/api/simulators/banker', {'allocation':[[0,1,0],[2,0,0],[3,0,2]],'maximum':[[7,5,3],[3,2,2],[9,0,2]],'available':[3,3,2]}),
        ('/api/simulators/deadlock', {'allocation':[[1,0],[0,1]],'request':[[0,1],[1,0]],'available':[0,0]}),
        ('/api/simulators/disk', {'algorithm':'SCAN','requests':[98,183,37,122,14,124,65,67],'head':53,'disk_size':200}),
        ('/api/simulators/producer-consumer', {'buffer_size':3,'items':6}),
        ('/api/simulators/dining-philosophers', {}),
        ('/api/simulators/paging', {'addresses':[10,11,22,35,42],'page_size':4,'num_frames':4}),
        ('/api/simulators/segmentation', {'segments':[{'base':100,'limit':50},{'base':1000,'limit':30}],'logical':[{'segment':0,'offset':20},{'segment':1,'offset':15},{'segment':1,'offset':35}]}),
        ('/api/simulators/threads', {}),
    ]
    for path, payload in sim_cases:
        r = client.post(path, json=payload)
        assert r.status_code == 200, f'{path}: {r.status_code} {r.text}'
        assert isinstance(r.json(), dict)

    # Code labs
    r = client.post('/api/labs/python', headers=auth(student), json={'source':'print("hello")'}); assert r.status_code == 200
    assert 'hello' in r.json().get('stdout','')
    r = client.post('/api/labs/test', headers=auth(student), json={'source':'print("hello")','expected_stdout':'hello','language':'python'}); assert r.status_code == 200 and r.json()['passed'] is True
    r = client.post('/api/labs/shell', headers=auth(student), json={'script':'echo hello'}); assert r.status_code == 200

    # Quiz generation + scoring
    r = client.post('/api/quizzes/generate', headers=auth(student), json={'topic':'Paging','difficulty':'medium','count':2,'kind':'mcq'})
    assert r.status_code == 200, r.text
    assessment = r.json()['assessment']
    answers = {str(q['id']): q['answer'] for q in assessment}
    r = client.post('/api/quizzes/score', headers=auth(student), json={'questions':assessment,'answers':answers,'topic':'Paging'})
    assert r.status_code == 200, r.text
    assert r.json()['score'] == 100

    # Evaluation endpoint
    r = client.post('/api/evaluation/run'); assert r.status_code == 200
    assert 'aggregate' in r.json()

    # Faculty/admin KB and RBAC
    r = client.get('/api/sources', headers=auth(faculty)); assert r.status_code == 200
    r = client.post('/api/rag/rebuild', headers=auth(faculty)); assert r.status_code == 200 and r.json()['sources'] >= 16
    r = client.get('/api/admin/students', headers=auth(faculty)); assert r.status_code == 200
    r = client.get('/api/admin/analytics', headers=auth(faculty)); assert r.status_code == 403
    r = client.get('/api/admin/analytics', headers=auth(admin)); assert r.status_code == 200

    # Faculty upload: small valid local source, then verify it is indexed
    name = f'faculty-test-{uuid.uuid4().hex[:8]}.md'
    content = b'# Faculty acceptance test\nPaging uses fixed-size pages and frames.\n'
    r = client.post('/api/sources/upload', headers=auth(faculty), files={'file': (name, io.BytesIO(content), 'text/markdown')})
    assert r.status_code == 200, r.text
    assert r.json()['ok'] is True

    # Unsupported upload must fail cleanly
    r = client.post('/api/sources/upload', headers=auth(faculty), files={'file': ('bad.exe', io.BytesIO(b'x'), 'application/octet-stream')})
    assert r.status_code == 400

    # OpenAPI + docs endpoints
    assert client.get('/openapi.json').status_code == 200
    assert client.get('/docs').status_code == 200
