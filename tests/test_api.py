from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from governancekit.server.main import create_app

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


def _begin(agent: TestClient, trace_id: str, activity: str) -> dict:
    response = agent.post(f"/traces/{trace_id}/activities", json={"activity": activity})
    assert response.status_code == 200, response.text
    return response.json()


def _finish(agent: TestClient, trace_id: str, instance_id: str, status: str) -> None:
    response = agent.post(
        f"/traces/{trace_id}/activities/{instance_id}/finish", json={"status": status}
    )
    assert response.status_code == 204, response.text


def _complete(agent: TestClient, trace_id: str, activity: str) -> None:
    """Begin an activity that must be allowed, and finish it as completed."""
    begun = _begin(agent, trace_id, activity)
    assert begun["decision"] == "allowed"
    _finish(agent, trace_id, begun["instance_id"], "completed")


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
    begin = client.post(f"/traces/{trace_id}/activities", json={"activity": "login"})
    running = client.get(f"/traces/{trace_id}/activities")
    end = client.post(f"/traces/{trace_id}/end")

    assert start.status_code == 403
    assert check.status_code == 403
    assert begin.status_code == 403
    assert running.status_code == 403
    assert end.status_code == 403


def test_agent_cannot_use_other_agents_trace(app, client, agent):
    other = _logged_in(app, *_register_agent(client))
    trace_id = _start_trace(agent, _add_model(client, EXISTENCE_DECL))

    instance_id = _begin(agent, trace_id, "login")["instance_id"]

    check = other.post(f"/traces/{trace_id}/check", json={"activity": "login"})
    begin = other.post(f"/traces/{trace_id}/activities", json={"activity": "login"})
    finish = other.post(
        f"/traces/{trace_id}/activities/{instance_id}/finish",
        json={"status": "completed"},
    )
    running = other.get(f"/traces/{trace_id}/activities")
    end = other.post(f"/traces/{trace_id}/end")

    assert check.status_code == 404
    assert begin.status_code == 404
    assert finish.status_code == 404
    assert running.status_code == 404
    assert end.status_code == 404
    # The trace is still running for its owner
    assert (
        agent.post(f"/traces/{trace_id}/check", json={"activity": "login"}).status_code
        == 200
    )


def test_started_trace_belongs_to_calling_agent(client, agent, agent_id):
    response = agent.post(
        "/traces", json={"model_id": _add_model(client, EXISTENCE_DECL)}
    )

    assert response.status_code == 201
    assert response.json()["agent_id"] == agent_id


def test_agent_works_on_parallel_traces(client, agent):
    model_id = _add_model(client, EXISTENCE_DECL)
    first = _start_trace(agent, model_id)
    second = _start_trace(agent, model_id)

    for trace_id in (first, second):
        _complete(agent, trace_id, "login")


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


@pytest.mark.xfail(reason="not built yet: POST /models does not return the constraints")
def test_add_model_returns_constraints(client):
    response = client.post("/models", json={"decl": EXISTENCE_DECL})

    assert response.status_code == 201
    constraints = response.json()["constraints"]
    assert len(constraints) == 1
    assert constraints[0]["template"] == "existence"
    assert constraints[0]["activation_activity"] == "login"


@pytest.mark.parametrize(
    "decl",
    ["Existence[login] |||", "activity a\nResponse[a, a]", "activity a\nFoo[a, a] |||"],
)
def test_add_invalid_model_returns_400(client, decl):
    response = client.post("/models", json={"decl": decl})

    assert response.status_code == 400


def test_list_models(client):
    existence_id = _add_model(client, EXISTENCE_DECL)
    precedence_id = _add_model(client, PRECEDENCE_DECL)

    response = client.get("/models")

    assert response.status_code == 200
    assert response.json()["models"] == [
        {"model_id": existence_id, "constraint_count": 1, "validate_payloads": False},
        {"model_id": precedence_id, "constraint_count": 1, "validate_payloads": False},
    ]


def test_get_model_returns_decl_text(client):
    model_id = _add_model(client, PRECEDENCE_DECL)

    response = client.get(f"/models/{model_id}")

    assert response.status_code == 200
    assert response.json() == {"model_id": model_id, "decl": PRECEDENCE_DECL}


def test_get_unknown_model_returns_404(client):
    assert client.get("/models/nope").status_code == 404


def test_viewing_models_requires_admin(agent):
    assert agent.get("/models").status_code == 403
    assert agent.get("/models/nope").status_code == 403


@pytest.mark.xfail(reason="not built yet: DELETE /models/{id}")
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


@pytest.mark.xfail(
    reason="violations are constraint sources, not {'constraint_id': ...}"
)
def test_end_trace_reports_missing_existence(client, agent):
    model_id = _add_model(client, EXISTENCE_DECL)
    satisfied = _start_trace(agent, model_id)
    unsatisfied = _start_trace(agent, model_id)
    _complete(agent, satisfied, "login")

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
    assert response.json() == {"decision": "allowed", "blocking": []}


def test_check_does_not_reserve(client, agent):
    trace_id = _start_trace(agent, _add_model(client, EXISTENCE_DECL))

    agent.post(f"/traces/{trace_id}/check", json={"activity": "login"})

    assert agent.get(f"/traces/{trace_id}/activities").json() == {"activities": []}


def test_check_on_unknown_trace_returns_404(agent):
    response = agent.post("/traces/nope/check", json={"activity": "login"})

    assert response.status_code == 404


def test_check_without_activity_returns_422(client, agent):
    trace_id = _start_trace(agent, _add_model(client, EXISTENCE_DECL))

    response = agent.post(f"/traces/{trace_id}/check", json={})

    assert response.status_code == 422


def test_invalid_event_returns_422_and_is_not_recorded(client, agent):
    response = client.post(
        "/models",
        json={
            "decl": "activity refund\nbind refund: amount, resource\n"
            "amount: integer between 0 and 100",
            "validate_payloads": True,
        },
    )
    model_id = response.json()["model_id"]
    trace_id = _start_trace(agent, model_id)
    event = {"activity": "refund", "payload": {"amount": 500.5}}

    check = agent.post(f"/traces/{trace_id}/check", json=event)
    begin = agent.post(f"/traces/{trace_id}/activities", json=event)

    expected = [
        "'amount' is not an integer between 0 and 100: 500.5",
        "missing attribute 'resource'",
    ]
    assert (check.status_code, check.json()["detail"]) == (422, expected)
    assert (begin.status_code, begin.json()["detail"]) == (422, expected)
    log = client.get(f"/traces/{trace_id}/audit").json()["auditLog"]
    assert [e["action"] for e in log] == ["start_trace"]
    models = client.get("/models").json()["models"]
    assert models[0]["validate_payloads"] is True


def test_begin_reserves_until_finish(client, agent):
    trace_id = _start_trace(agent, _add_model(client, EXISTENCE_DECL))

    begun = _begin(agent, trace_id, "login")
    running = agent.get(f"/traces/{trace_id}/activities").json()["activities"]

    assert begun["decision"] == "allowed"
    assert begun["blocking"] == []
    assert [(a["instance_id"], a["activity"]) for a in running] == [
        (begun["instance_id"], "login")
    ]

    _finish(agent, trace_id, begun["instance_id"], "completed")
    assert agent.get(f"/traces/{trace_id}/activities").json() == {"activities": []}


def test_precedence_decisions_follow_the_target(client, agent):
    trace_id = _start_trace(agent, _add_model(client, PRECEDENCE_DECL))
    blocking = ["Precedence[authorize, delete] |||"]

    assert _begin(agent, trace_id, "delete") == {
        "decision": "denied",
        "instance_id": None,
        "blocking": blocking,
    }

    authorize = _begin(agent, trace_id, "authorize")["instance_id"]
    assert _begin(agent, trace_id, "delete")["decision"] == "wait"

    _finish(agent, trace_id, authorize, "failed")
    assert _begin(agent, trace_id, "delete")["decision"] == "denied"

    _complete(agent, trace_id, "authorize")
    assert _begin(agent, trace_id, "delete")["decision"] == "allowed"


def test_finish_unknown_instance_returns_404(client, agent):
    trace_id = _start_trace(agent, _add_model(client, EXISTENCE_DECL))

    response = agent.post(
        f"/traces/{trace_id}/activities/nope/finish", json={"status": "completed"}
    )

    assert response.status_code == 404


def test_finish_with_unknown_status_returns_422(client, agent):
    trace_id = _start_trace(agent, _add_model(client, EXISTENCE_DECL))
    instance_id = _begin(agent, trace_id, "login")["instance_id"]

    response = agent.post(
        f"/traces/{trace_id}/activities/{instance_id}/finish", json={"status": "done"}
    )

    assert response.status_code == 422


def test_end_with_running_activities_returns_409(client, agent):
    trace_id = _start_trace(agent, _add_model(client, EXISTENCE_DECL))
    _begin(agent, trace_id, "login")

    response = agent.post(f"/traces/{trace_id}/end")

    assert response.status_code == 409
    # The trace is still there
    assert agent.get(f"/traces/{trace_id}/activities").status_code == 200


def test_end_with_abort_running_aborts_them(client, agent):
    trace_id = _start_trace(agent, _add_model(client, EXISTENCE_DECL))
    instance_id = _begin(agent, trace_id, "login")["instance_id"]

    response = agent.post(f"/traces/{trace_id}/end", params={"abort_running": True})

    assert response.status_code == 200
    assert response.json()["conformant"] is False  # login never completed
    finishes = [
        e for e in client.get("/audit").json()["auditLog"] if e["action"] == "finish"
    ]
    assert [(e["instance_id"], e["status"]) for e in finishes] == [
        (instance_id, "aborted")
    ]


def test_audit_records_begin_and_finish(client, agent):
    trace_id = _start_trace(agent, _add_model(client, EXISTENCE_DECL))
    _complete(agent, trace_id, "login")

    log = client.get("/audit").json()["auditLog"]

    begin, finish = (e for e in log if e["action"] in ("begin", "finish"))
    assert (begin["decision"], begin["activity"]) == ("allowed", "login")
    assert (finish["status"], finish["instance_id"]) == (
        "completed",
        begin["instance_id"],
    )


def test_trace_audit_contains_only_that_trace(client, agent):
    model_id = _add_model(client, EXISTENCE_DECL)
    trace_id = _start_trace(agent, model_id)
    _start_trace(agent, model_id)  # another trace, which must not show up
    _complete(agent, trace_id, "login")

    log = client.get(f"/traces/{trace_id}/audit").json()["auditLog"]

    assert {e["trace_id"] for e in log} == {trace_id}
    assert [e["action"] for e in log] == ["start_trace", "begin", "finish"]


def test_trace_audit_is_kept_after_trace_ends(client, agent):
    trace_id = _start_trace(agent, _add_model(client, EXISTENCE_DECL))
    agent.post(f"/traces/{trace_id}/end")

    response = client.get(f"/traces/{trace_id}/audit")

    assert response.status_code == 200
    assert [e["action"] for e in response.json()["auditLog"]] == [
        "start_trace",
        "end_trace",
    ]


def test_trace_audit_of_unknown_trace_returns_404(client):
    assert client.get("/traces/unknown/audit").status_code == 404


def test_trace_audit_requires_admin(client, agent):
    trace_id = _start_trace(agent, _add_model(client, EXISTENCE_DECL))

    assert agent.get(f"/traces/{trace_id}/audit").status_code == 403


def test_added_agent_can_work_on_trace(app, client, agent):
    trace_id = _start_trace(agent, _add_model(client, EXISTENCE_DECL))
    other_id, other_secret = _register_agent(client, "other-agent")
    other = _logged_in(app, other_id, other_secret)

    response = client.post(f"/traces/{trace_id}/agents", json={"agent_id": other_id})

    assert response.status_code == 200
    assert other_id in response.json()["agent_ids"]
    _complete(other, trace_id, "login")
    log = client.get(f"/traces/{trace_id}/audit").json()["auditLog"]
    assert other_id in {e["agent_id"] for e in log}


def test_add_unknown_agent_to_trace_returns_404(client, agent):
    trace_id = _start_trace(agent, _add_model(client, EXISTENCE_DECL))

    response = client.post(f"/traces/{trace_id}/agents", json={"agent_id": "nobody"})

    assert response.status_code == 404


def test_add_agent_to_ended_trace_returns_409(client, agent, agent_id):
    trace_id = _start_trace(agent, _add_model(client, EXISTENCE_DECL))
    agent.post(f"/traces/{trace_id}/end")

    response = client.post(f"/traces/{trace_id}/agents", json={"agent_id": agent_id})

    assert response.status_code == 409


def test_adding_agents_requires_admin(client, agent, agent_id):
    trace_id = _start_trace(agent, _add_model(client, EXISTENCE_DECL))

    response = agent.post(f"/traces/{trace_id}/agents", json={"agent_id": agent_id})

    assert response.status_code == 403


def test_list_traces_filters_running_and_ended(client, agent, agent_id):
    model_id = _add_model(client, EXISTENCE_DECL)
    running_id = _start_trace(agent, model_id)
    ended_id = _start_trace(agent, model_id)
    agent.post(f"/traces/{ended_id}/end")

    all_traces = client.get("/traces").json()["traces"]
    running = client.get("/traces", params={"ended": False}).json()["traces"]
    ended = client.get("/traces", params={"ended": True}).json()["traces"]

    assert [t["trace_id"] for t in all_traces] == [ended_id, running_id]
    assert [t["trace_id"] for t in running] == [running_id]
    assert [t["trace_id"] for t in ended] == [ended_id]
    assert running[0]["ended_at"] is None and running[0]["violations"] is None
    assert ended[0]["violations"] == ["Existence[login, 1] |||"]
    assert ended[0]["agent_ids"] == [agent_id]
    assert ended[0]["entry_count"] == 2  # start and end


def test_listing_traces_requires_admin(agent):
    assert agent.get("/traces").status_code == 403


def test_list_monitors_shows_running_traces_only(client, agent, agent_id):
    model_id = _add_model(client, EXISTENCE_DECL)
    running_id = _start_trace(agent, model_id)
    ended_id = _start_trace(agent, model_id)
    agent.post(f"/traces/{ended_id}/end")
    instance_id = _begin(agent, running_id, "login")["instance_id"]

    monitors = client.get("/monitors").json()["monitors"]

    assert [m["trace_id"] for m in monitors] == [running_id]
    monitor = monitors[0]
    assert (monitor["model_id"], monitor["agent_ids"]) == (model_id, [agent_id])
    assert [(r["instance_id"], r["activity"]) for r in monitor["running"]] == [
        (instance_id, "login")
    ]
    # login has begun but not completed, so Existence is not satisfied yet
    assert monitor["violations"] == ["Existence[login, 1] |||"]


def test_listing_monitors_requires_admin(agent):
    assert agent.get("/monitors").status_code == 403
