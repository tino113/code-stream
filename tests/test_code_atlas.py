from pathlib import Path
import sys

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from backend.app.main import app


client = TestClient(app)


def test_code_atlas_endpoint_shape():
    snippet = """
class Worker:
    def process(self, items):
        for item in items:
            try:
                with open(item) as f:
                    print(f.read())
            except OSError:
                print('bad file')
"""

    response = client.post(
        "/api/code-atlas",
        json={"files": [{"path": "sample.py", "content": snippet}]},
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"nodes", "edges", "clusters"}
    assert isinstance(body["nodes"], list)
    assert isinstance(body["edges"], list)
    assert isinstance(body["clusters"], dict)

    kinds = {node["kind"] for node in body["nodes"]}
    assert {"file", "class", "function", "loop", "exception", "io_call"}.issubset(kinds)


def test_code_atlas_is_deterministic_for_same_payload():
    snippet = """
def run(paths):
    for path in paths:
        try:
            data = open(path).read()
            print(data)
        except Exception:
            print('error')
"""

    payload = {
        "files": [
            {"path": "b.py", "content": snippet},
            {"path": "a.py", "content": snippet},
        ]
    }

    first = client.post("/api/code-atlas", json=payload)
    second = client.post("/api/code-atlas", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
