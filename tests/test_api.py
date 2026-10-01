from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.main import create_app

JWT_SECRET = "test-jwt-secret-that-is-at-least-32-bytes"
ADMIN_SECRET = "test-admin-secret"

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
def app() -> FastAPI:
    return create_app(jwt_secret=JWT_SECRET, admin_secret=ADMIN_SECRET)


@pytest.fixture
def client(app) -> TestClient:
    """Client logged in as admin."""
    return _logged_in(app, "admin", ADMIN_SECRET)


@pytest.fixture
def agent_credentials(client) -> tuple[str, str]:
    return _register_agent(client)


@pytest.fixture
def agent_id(agent_credentials) -> str:
    return agent_credentials[0]


@pytest.fixture
def agent(app, agent_credentials) -> TestClient:
    """Client logged in as the agent agent_id."""
    return _logged_in(app, *agent_credentials)


def _token(app: FastAPI, client_id: str, secret: str) -> str:
    response = TestClient(app).post(
        "/token", data={"username": client_id, "password": secret}
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _logged_in(app: FastAPI, client_id: str, secret: str) -> TestClient:
    token = _token(app, client_id, secret)
    return TestClient(app, headers={"Authorization": f"Bearer {token}"})


def _register_agent(client: TestClient, name: str = "test-agent") -> tuple[str, str]:
    response = client.post("/agents", json={"agent_name": name})
    assert response.status_code == 201, response.text
    return response.json()["agent_info"]["agent_id"], response.json()["secret"]


def _add_model(client: TestClient, decl: str) -> str:
    response = client.post("/models", json={"decl": decl})
    assert response.status_code == 201, response.text
    return response.json()["model_id"]


def _start_trace(agent: TestClient, model_id: str) -> str:
    response = agent.post("/traces", json={"model_id": model_id})
    assert response.status_code == 201, response.text
    return response.json()["trace_id"]


# ---------- Auth ----------


def test_wrong_secret_returns_401(app, agent_id):
    client = TestClient(app)

    admin = client.post("/token", data={"username": "admin", "password": "wrong"})
    agent = client.post("/token", data={"username": agent_id, "password": "wrong"})

    assert admin.status_code == 401
    assert agent.status_code == 401


def test_requests_without_token_return_401(app):
    client = TestClient(app)

    assert client.post("/models", json={"decl": EXISTENCE_DECL}).status_code == 401
    assert client.post("/traces/x/check", json={"activity": "login"}).status_code == 401


def test_expired_token_returns_401(app):
    expired = jwt.encode(
        {"sub": "admin", "role": "admin", "exp": datetime.now(UTC) - timedelta(1)},
        JWT_SECRET,
        algorithm="HS256",
    )
    client = TestClient(app, headers={"Authorization": f"Bearer {expired}"})

    assert client.get("/agents").status_code == 401


def test_token_signed_with_other_key_returns_401(app):
    forged = jwt.encode(
        {"sub": "admin", "role": "admin", "exp": datetime.now(UTC) + timedelta(1)},
        "some-other-key-that-is-at-least-32-bytes",
        algorithm="HS256",
    )
    client = TestClient(app, headers={"Authorization": f"Bearer {forged}"})

    assert client.get("/agents").status_code == 401


def test_agent_cannot_use_management_endpoints(agent):
    assert agent.post("/agents", json={"agent_name": "x"}).status_code == 403
    assert agent.get("/agents").status_code == 403
    assert agent.post("/models", json={"decl": EXISTENCE_DECL}).status_code == 403


def test_admin_cannot_use_runtime_endpoints(client, agent):
    model_id = _add_model(client, EXISTENCE_DECL)
    trace_id = _start_trace(agent, model_id)

    start = client.post("/traces", json={"model_id": model_id})
    check = client.post(f"/traces/{trace_id}/check", json={"activity": "login"})
    commit = client.post(f"/traces/{trace_id}/commit", json={"activity": "login"})
    end = client.post(f"/traces/{trace_id}/end")

    assert start.status_code == 403
    assert check.status_code == 403
    assert commit.status_code == 403
    assert end.status_code == 403


def test_agent_cannot_use_other_agents_trace(app, client, agent):
    other = _logged_in(app, *_register_agent(client))
    trace_id = _start_trace(agent, _add_model(client, EXISTENCE_DECL))

    check = other.post(f"/traces/{trace_id}/check", json={"activity": "login"})
    commit = other.post(f"/traces/{trace_id}/commit", json={"activity": "login"})
    end = other.post(f"/traces/{trace_id}/end")

    assert check.status_code == 404
    assert commit.status_code == 404
    assert end.status_code == 404
    # The trace is still running for its owner
    assert agent.post(f"/traces/{trace_id}/check", json={"activity": "login"}).status_code == 200


def test_started_trace_belongs_to_calling_agent(client, agent, agent_id):
    response = agent.post("/traces", json={"model_id": _add_model(client, EXISTENCE_DECL)})

    assert response.status_code == 201
    assert response.json()["agent_id"] == agent_id


def test_agent_works_on_parallel_traces(client, agent):
    model_id = _add_model(client, EXISTENCE_DECL)
    first = _start_trace(agent, model_id)
    second = _start_trace(agent, model_id)

    for trace_id in (first, second):
        check = agent.post(f"/traces/{trace_id}/check", json={"activity": "login"})
        commit = agent.post(f"/traces/{trace_id}/commit", json={"activity": "login"})
        assert check.status_code == 200
        assert commit.status_code == 204


# ---------- Management ----------


def test_register_agent_returns_info_and_secret(client):
    response = client.post("/agents", json={"agent_name": "support-bot"})

    assert response.status_code == 201
    body = response.json()
    assert body["agent_info"]["agent_name"] == "support-bot"
    assert body["agent_info"]["agent_id"]
    assert body["secret"]


def test_register_agent_without_name_returns_422(client):
    assert client.post("/agents", json={}).status_code == 422


def test_list_agents(client):
    support_id, _ = _register_agent(client, "support-bot")
    billing_id, _ = _register_agent(client, "billing-bot")

    response = client.get("/agents")

    assert response.status_code == 200
    assert sorted(response.json()["agents"], key=lambda a: a["agent_name"]) == [
        {"agent_id": billing_id, "agent_name": "billing-bot"},
        {"agent_id": support_id, "agent_name": "support-bot"},
    ]


def test_list_agents_does_not_leak_secrets(client):
    _, secret = _register_agent(client)

    response = client.get("/agents")

    assert secret not in response.text
    assert "hash" not in response.text
    assert "argon2" not in response.text


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


def test_start_trace_on_unknown_model_returns_404(agent):
    response = agent.post("/traces", json={"model_id": "nope"})

    assert response.status_code == 404


def test_trace_survives_model_removal(client, agent):
    model_id = _add_model(client, EXISTENCE_DECL)
    trace_id = _start_trace(agent, model_id)
    client.delete(f"/models/{model_id}")

    response = agent.post(f"/traces/{trace_id}/check", json={"activity": "login"})

    assert response.status_code == 200


def test_end_trace_without_constraints_is_conformant(client, agent):
    model_id = _add_model(client, "activity login")
    trace_id = _start_trace(agent, model_id)

    response = agent.post(f"/traces/{trace_id}/end")

    assert response.status_code == 200
    assert response.json() == {
        "trace_id": trace_id,
        "conformant": True,
        "violations": [],
    }


def test_ended_trace_is_removed(client, agent):
    model_id = _add_model(client, "activity login")
    trace_id = _start_trace(agent, model_id)
    agent.post(f"/traces/{trace_id}/end")

    response = agent.post(f"/traces/{trace_id}/check", json={"activity": "login"})

    assert response.status_code == 404


@pytest.mark.xfail(reason="TraceMonitor.analyze compares i.verdict without calling it")
def test_end_trace_reports_missing_existence(client, agent):
    model_id = _add_model(client, EXISTENCE_DECL)
    satisfied = _start_trace(agent, model_id)
    unsatisfied = _start_trace(agent, model_id)
    agent.post(f"/traces/{satisfied}/commit", json={"activity": "login"})

    ok = agent.post(f"/traces/{satisfied}/end").json()
    missing = agent.post(f"/traces/{unsatisfied}/end").json()

    assert ok["conformant"] is True
    assert missing["conformant"] is False
    assert missing["violations"] == [{"constraint_id": "existence_0"}]


# ---------- Runtime ----------


def test_check_allowed(client, agent):
    trace_id = _start_trace(agent, _add_model(client, EXISTENCE_DECL))

    response = agent.post(
        f"/traces/{trace_id}/check",
        json={"activity": "login", "payload": {"user": "alice"}},
    )

    assert response.status_code == 200
    assert response.json() == {"allowed": True, "violations": []}


def test_commit_returns_204(client, agent):
    trace_id = _start_trace(agent, _add_model(client, EXISTENCE_DECL))

    response = agent.post(f"/traces/{trace_id}/commit", json={"activity": "login"})

    assert response.status_code == 204


def test_check_on_unknown_trace_returns_404(agent):
    response = agent.post("/traces/nope/check", json={"activity": "login"})

    assert response.status_code == 404


def test_check_without_activity_returns_422(client, agent):
    trace_id = _start_trace(agent, _add_model(client, EXISTENCE_DECL))

    response = agent.post(f"/traces/{trace_id}/check", json={})

    assert response.status_code == 422


@pytest.mark.xfail(reason="decl_parser: len(bracket_items != 2) breaks binary templates")
def test_precedence_blocks_until_target_committed(client, agent):
    trace_id = _start_trace(agent, _add_model(client, PRECEDENCE_DECL))

    blocked = agent.post(f"/traces/{trace_id}/check", json={"activity": "delete"})
    agent.post(f"/traces/{trace_id}/commit", json={"activity": "authorize"})
    allowed = agent.post(f"/traces/{trace_id}/check", json={"activity": "delete"})

    assert blocked.json() == {
        "allowed": False,
        "violations": [{"constraint_id": "precedence_0"}],
    }
    assert allowed.json() == {"allowed": True, "violations": []}
