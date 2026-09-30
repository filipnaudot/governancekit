"""
GovernanceKit web server.

Management endpoints: add/remove models, start/end traces.
Runtime endpoints: check and commit agent actions against a trace.

Management endpoints require an admin token, runtime endpoints an agent
token. The admin secret is read from GK_ADMIN_SECRET and the JWT signing key
from GK_JWT_SECRET; if unset, random ones are generated at startup.
"""

import logging
import os
import secrets
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

import jwt
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import AwareDatetime, BaseModel, Field

from api.auth import Authenticator, Principal, Role
from core.events import Event
from core.monitor_registry import MonitorRegistry

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# ---------- Request / response schemas ----------


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RegisterAgentResponse(BaseModel):
    agent_id: str
    secret: str = Field(description="Shown only once; the server keeps a hash")


class AddModelRequest(BaseModel):
    decl: str = Field(description="MP-DECLARE model as .decl text")


class AddModelResponse(BaseModel):
    model_id: str


class StartTraceRequest(BaseModel):
    model_id: str
    agent_id: str = Field(description="The agent allowed to check and commit")


class TraceOut(BaseModel):
    trace_id: str
    model_id: str
    agent_id: str


class EventRequest(BaseModel):
    activity: str
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: AwareDatetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Defaults to the server's current time",
    )


class CheckResponse(BaseModel):
    allowed: bool
    violations: list[str]


class EndTraceResponse(BaseModel):
    trace_id: str
    conformant: bool
    violations: list[str]


# ---------- App ----------


def create_app(
    jwt_secret: str | None = None, admin_secret: str | None = None
) -> FastAPI:
    app = FastAPI(title="GovernanceKit")

    jwt_secret = jwt_secret or os.environ.get("GK_JWT_SECRET") or secrets.token_hex(32)
    admin_secret = admin_secret or os.environ.get("GK_ADMIN_SECRET")
    if not admin_secret:
        admin_secret = secrets.token_urlsafe(16)
        logger.warning("GK_ADMIN_SECRET is not set. Admin secret: %s", admin_secret)

    # In-memory state: lost when the server restarts
    registry = MonitorRegistry()
    auth = Authenticator(jwt_secret=jwt_secret, admin_secret=admin_secret)
    trace_agents: dict[str, str] = {}  # trace ID -> ID of the agent working on it

    # --- Auth ---

    def current_principal(token: Annotated[str, Depends(oauth2_scheme)]) -> Principal:
        try:
            return auth.verify_token(token)
        except jwt.InvalidTokenError as e:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                "Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            ) from e

    def require_admin(
        principal: Annotated[Principal, Depends(current_principal)],
    ) -> Principal:
        if principal.role != Role.ADMIN:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Requires an admin token")
        return principal

    def require_agent(
        principal: Annotated[Principal, Depends(current_principal)],
    ) -> Principal:
        if principal.role != Role.AGENT:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Requires an agent token")
        return principal

    def check_trace_owner(trace_id: str, agent: Principal) -> None:
        # Another agent's trace is reported as missing, so its ID is not revealed
        if trace_agents.get(trace_id) != agent.id:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, f"Trace not found: {trace_id!r}"
            )

    @app.post("/token", tags=["auth"])
    def login(form: Annotated[OAuth2PasswordRequestForm, Depends()]) -> TokenResponse:
        """Exchange an ID (username) and secret (password) for a bearer token."""
        principal = auth.authenticate(form.username, form.password)
        if principal is None:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                "Wrong ID or secret",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return TokenResponse(access_token=auth.create_token(principal))

    # --- Management ---

    @app.post(
        "/agents",
        status_code=status.HTTP_201_CREATED,
        tags=["management"],
        dependencies=[Depends(require_admin)],
    )
    def register_agent() -> RegisterAgentResponse:
        """Register an agent and return its ID and secret."""
        agent_id, secret = auth.register_agent()
        return RegisterAgentResponse(agent_id=agent_id, secret=secret)

    @app.post(
        "/models",
        status_code=status.HTTP_201_CREATED,
        tags=["management"],
        dependencies=[Depends(require_admin)],
    )
    def add_model(body: AddModelRequest) -> AddModelResponse:
        """Register an MP-Declare model and return its generated ID."""
        model_id = str(uuid.uuid4())
        try:
            registry.add_model(model_id=model_id, model_text=body.decl)
        except ValueError as e:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, f"Unable to add model: {e}"
            ) from e
        return AddModelResponse(model_id=model_id)

    @app.post(
        "/traces",
        status_code=status.HTTP_201_CREATED,
        tags=["management"],
        dependencies=[Depends(require_admin)],
    )
    def start_trace(body: StartTraceRequest) -> TraceOut:
        if body.agent_id not in auth.agents:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, f"Unknown agent: {body.agent_id!r}"
            )
        trace_id = str(uuid.uuid4())
        try:
            registry.start_monitor(model_id=body.model_id, trace_id=trace_id)
        except KeyError as e:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown model: {e}") from e
        trace_agents[trace_id] = body.agent_id
        return TraceOut(trace_id=trace_id, model_id=body.model_id, agent_id=body.agent_id)

    @app.post(
        "/traces/{trace_id}/end",
        tags=["management"],
        dependencies=[Depends(require_admin)],
    )
    def end_trace(trace_id: str) -> EndTraceResponse:
        try:
            violations = registry.violations(trace_id=trace_id)
            registry.end_monitor(trace_id=trace_id)
        except KeyError as e:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, f"Trace not found: {e}"
            ) from e
        trace_agents.pop(trace_id, None)
        return EndTraceResponse(
            trace_id=trace_id,
            conformant=not violations,
            violations=violations,
        )

    # --- Runtime ---

    @app.post("/traces/{trace_id}/check", tags=["runtime"])
    def check(
        trace_id: str,
        body: EventRequest,
        agent: Annotated[Principal, Depends(require_agent)],
    ) -> CheckResponse:
        check_trace_owner(trace_id, agent)
        event = Event(
            activity=body.activity, timestamp=body.timestamp, payload=body.payload
        )
        try:
            allowed, violations = registry.check_event(trace_id=trace_id, event=event)
        except KeyError as e:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, f"Trace not found: {e}"
            ) from e
        return CheckResponse(allowed=allowed, violations=violations)

    @app.post(
        "/traces/{trace_id}/commit",
        status_code=status.HTTP_204_NO_CONTENT,
        tags=["runtime"],
    )
    def commit(
        trace_id: str,
        body: EventRequest,
        agent: Annotated[Principal, Depends(require_agent)],
    ) -> None:
        check_trace_owner(trace_id, agent)
        event = Event(
            activity=body.activity, timestamp=body.timestamp, payload=body.payload
        )
        try:
            registry.commit_event(trace_id=trace_id, event=event)
        except KeyError as e:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, f"Trace not found: {e}"
            ) from e

    return app


app = create_app()
