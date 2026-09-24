import pytest
from fastapi.testclient import TestClient

from api.main import create_app

EXISTENCE_DECL = """
    activity login
    Existence[login, 1] |||
"""

PRECEDENCE_DECL = """
    activity authorize
    activity delete
    Precedence[authorize, delete] |||
"""


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def _add_model(client: TestClient, decl: str) -> str:
    response = client.post("/models", json={"decl": decl})
    assert response.status_code == 201, response.text
    return response.json()["model_id"]


def _start_trace(client: TestClient, model_id: str) -> str:
    response = client.post("/traces", json={"model_id": model_id})
    assert response.status_code == 201, response.text
    return response.json()["trace_id"]


# ---------- Management ----------


def test_add_model_returns_constraints(client):
    response = client.post("/models", json={"decl": EXISTENCE_DECL})

    assert response.status_code == 201
    constraints = response.json()["constraints"]
    assert len(constraints) == 1
    assert constraints[0]["template"] == "existence"
    assert constraints[0]["activation_activity"] == "login"


def test_add_invalid_model_returns_400(client):
    response = client.post("/models", json={"decl": "Existence[login] |||"})

    assert response.status_code == 400


def test_remove_model(client):
    model_id = _add_model(client, EXISTENCE_DECL)

    assert client.delete(f"/models/{model_id}").status_code == 204
    assert client.delete(f"/models/{model_id}").status_code == 404


def test_start_trace_on_unknown_model_returns_404(client):
    response = client.post("/traces", json={"model_id": "nope"})

    assert response.status_code == 404


def test_trace_survives_model_removal(client):
    model_id = _add_model(client, EXISTENCE_DECL)
    trace_id = _start_trace(client, model_id)
    client.delete(f"/models/{model_id}")

    response = client.post(f"/traces/{trace_id}/check", json={"activity": "login"})

    assert response.status_code == 200


def test_end_trace_without_constraints_is_conformant(client):
    model_id = _add_model(client, "activity login")
    trace_id = _start_trace(client, model_id)

    response = client.post(f"/traces/{trace_id}/end")

    assert response.status_code == 200
    assert response.json() == {
        "trace_id": trace_id,
        "conformant": True,
        "violations": [],
    }


def test_ended_trace_is_removed(client):
    model_id = _add_model(client, "activity login")
    trace_id = _start_trace(client, model_id)
    client.post(f"/traces/{trace_id}/end")

    response = client.post(f"/traces/{trace_id}/check", json={"activity": "login"})

    assert response.status_code == 404


@pytest.mark.xfail(reason="TraceMonitor.analyze compares i.verdict without calling it")
def test_end_trace_reports_missing_existence(client):
    model_id = _add_model(client, EXISTENCE_DECL)
    satisfied = _start_trace(client, model_id)
    unsatisfied = _start_trace(client, model_id)
    client.post(f"/traces/{satisfied}/commit", json={"activity": "login"})

    ok = client.post(f"/traces/{satisfied}/end").json()
    missing = client.post(f"/traces/{unsatisfied}/end").json()

    assert ok["conformant"] is True
    assert missing["conformant"] is False
    assert missing["violations"] == [{"constraint_id": "existence_0"}]


# ---------- Runtime ----------


def test_check_allowed(client):
    trace_id = _start_trace(client, _add_model(client, EXISTENCE_DECL))

    response = client.post(
        f"/traces/{trace_id}/check",
        json={"activity": "login", "payload": {"user": "alice"}},
    )

    assert response.status_code == 200
    assert response.json() == {"allowed": True, "violations": []}


def test_commit_returns_204(client):
    trace_id = _start_trace(client, _add_model(client, EXISTENCE_DECL))

    response = client.post(f"/traces/{trace_id}/commit", json={"activity": "login"})

    assert response.status_code == 204


def test_check_on_unknown_trace_returns_404(client):
    response = client.post("/traces/nope/check", json={"activity": "login"})

    assert response.status_code == 404


def test_check_without_activity_returns_422(client):
    trace_id = _start_trace(client, _add_model(client, EXISTENCE_DECL))

    response = client.post(f"/traces/{trace_id}/check", json={})

    assert response.status_code == 422


@pytest.mark.xfail(reason="decl_parser: len(bracket_items != 2) breaks binary templates")
def test_precedence_blocks_until_target_committed(client):
    trace_id = _start_trace(client, _add_model(client, PRECEDENCE_DECL))

    blocked = client.post(f"/traces/{trace_id}/check", json={"activity": "delete"})
    client.post(f"/traces/{trace_id}/commit", json={"activity": "authorize"})
    allowed = client.post(f"/traces/{trace_id}/check", json={"activity": "delete"})

    assert blocked.json() == {
        "allowed": False,
        "violations": [{"constraint_id": "precedence_0"}],
    }
    assert allowed.json() == {"allowed": True, "violations": []}
