"""API integration tests. Run inside the Docker stack:  docker compose run --rm api pytest -q tests/test_api.py

They need FastAPI, PostgreSQL and the other service dependencies, so they are skipped automatically when
FastAPI is not installed. The LLM is disabled so the deterministic extractive path is exercised."""
import json
import os

import pytest

pytest.importorskip("fastapi")
os.environ["OSTUTOR_TEST_MODE"] = "1"
os.environ["LLM_BASE_URL"] = ""

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.exercises import EXERCISES  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def auth(client, email="student@ostutor.local", pw="Student123!"):
    r = client.post("/api/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def test_health_and_topics(client):
    h = client.get("/health").json()
    assert h["status"] == "ok" and h["database"] == "ok"
    topics = client.get("/api/topics").json()
    assert len(topics) >= 20 and all(t["questions"] >= 3 for t in topics)


def test_auth_rules(client):
    assert client.get("/api/auth/me").status_code in (401, 403)
    assert client.post("/api/auth/login", json={"email": "student@ostutor.local", "password": "bad"}).status_code == 401
    assert client.post("/api/auth/register", json={"email": "x", "password": "short", "name": "n"}).status_code == 422
    assert client.get("/api/sources", headers=auth(client)).status_code == 403
    assert client.get("/api/sources", headers=auth(client, "faculty@ostutor.local", "Faculty123!")).status_code == 200


def test_tutor_grounded_and_conversation(client):
    h = auth(client)
    r = client.post("/api/tutor/chat", headers=h, json={"message": "What is the convoy effect in FCFS?", "mode": "exam"}).json()
    assert r["citations"] and r["retrieved"] > 0 and not r["abstained"]
    assert any("[S1]" in s["text"] or s["refs"] for s in r["support"]["sentences"])
    follow = client.post("/api/tutor/chat", headers=h, json={"message": "and SJF?", "conversation_id": r["conversation_id"]}).json()
    assert follow["conversation_id"] == r["conversation_id"]
    convo = client.get(f"/api/tutor/conversations/{r['conversation_id']}", headers=h).json()
    assert len(convo["messages"]) == 4
    fb = client.post(f"/api/tutor/messages/{r['message_id']}/feedback", headers=h, json={"value": 1}).json()
    assert fb["feedback"] == 1
    assert client.delete(f"/api/tutor/conversations/{r['conversation_id']}", headers=h).json()["ok"]


def test_tutor_abstains_off_topic(client):
    r = client.post("/api/tutor/chat", headers=auth(client), json={"message": "Who won the football world cup?"}).json()
    assert r["abstained"] and r["citations"] == []


def test_conversation_isolation(client):
    r = client.post("/api/tutor/chat", headers=auth(client), json={"message": "What is a thread?"}).json()
    other = auth(client, "faculty@ostutor.local", "Faculty123!")
    assert client.get(f"/api/tutor/conversations/{r['conversation_id']}", headers=other).status_code == 404


def test_stream_events(client):
    events = []
    with client.stream("POST", "/api/tutor/stream", headers=auth(client), json={"message": "Explain round robin scheduling"}) as resp:
        name = None
        for line in resp.iter_lines():
            if line.startswith("event:"):
                name = line.split(":", 1)[1].strip()
            elif line.startswith("data:") and name:
                events.append((name, json.loads(line[5:])))
    names = [n for n, _ in events]
    assert names[0] == "meta" and names[-1] == "done"
    assert events[-1][1]["citations"]


def test_quiz_is_scored_on_the_server(client):
    h = auth(client)
    q = client.post("/api/quizzes/generate", headers=h, json={"topic": "Paging", "count": 3}).json()["assessment"]
    assert q and all("answer" not in x for x in q)
    s = client.post("/api/quizzes/score", headers=h, json={"topic": "Paging", "answers": {str(x["id"]): "A" for x in q}}).json()
    assert s["total"] == len(q) and all("explanation" in r for r in s["results"])
    forged = client.post("/api/quizzes/score", headers=h, json={"topic": "Paging", "answers": {"999999": "A"}})
    assert forged.status_code == 422


def test_viva(client):
    h = auth(client)
    q = client.post("/api/quizzes/generate", headers=h, json={"topic": "Deadlocks", "kind": "viva", "count": 1}).json()["assessment"][0]
    g = client.post("/api/quizzes/viva-grade", headers=h, json={"question_id": q["id"], "answer": "mutual exclusion hold and wait no preemption circular wait"}).json()
    assert g["score"] >= 70


def test_labs_require_auth_and_run(client):
    assert client.post("/api/labs/python", json={"source": "print(1)"}).status_code in (401, 403)
    h = auth(client)
    assert client.post("/api/labs/python", headers=h, json={"source": "print(6*7)"}).json()["stdout"].strip() == "42"
    assert client.post("/api/labs/python", headers=h, json={"source": "import os"}).json()["ok"] is False
    ex = EXERCISES[0]
    r = client.post("/api/labs/test", headers=h, json={"exercise_id": ex["id"], "source": ex["solution"]}).json()
    assert r["passed"]
    assert all("solution" not in e for e in client.get("/api/labs/exercises", headers=h).json())


def test_simulators(client):
    r = client.post("/api/simulators/disk", json={"algorithm": "SCAN", "requests": [98, 183, 37, 122, 14, 124, 65, 67], "head": 53, "disk_size": 200, "direction": "down"}).json()
    assert r["movement"] == 236
    bad = client.post("/api/simulators/cpu", json={"algorithm": "FCFS", "processes": [{"pid": "A", "burst": 0}]})
    assert bad.status_code == 422
    assert client.post("/api/simulators/dining-philosophers", json={"strategy": "naive"}).json()["deadlock"]


def test_retrieval_lab_and_evaluation(client):
    h = auth(client)
    r = client.post("/api/rag/search", headers=h, json={"query": "what is a TLB"}).json()
    assert r["hits"] and "bm25" in r["hits"][0]["scores"]
    f = auth(client, "faculty@ostutor.local", "Faculty123!")
    ev = client.post("/api/evaluation/retrieval", headers=f).json()
    assert ev["aggregate"]["recall_at_k"] >= 0.9
    assert client.post("/api/evaluation/retrieval", headers=h).status_code == 403
