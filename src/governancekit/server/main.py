"""
GovernanceKit web server.

Management endpoints: register agents, add models, read the audit log.
Runtime endpoints: start/end traces, and check, begin and finish activities.
Several activities may run at the same time on one trace.

Management endpoints require an admin token, runtime endpoints an agent
token. The admin secret is read from GK_ADMIN_SECRET and the JWT signing key
from GK_JWT_SECRET; if unset, random ones are generated at startup.

The endpoints live in routers, one module per area: auth, agents, models,
traces, monitors and audit.
"""

import logging
import os
import secrets

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from governancekit.engine.monitor_registry import MonitorRegistry
from governancekit.server import agents, audit, auth, models, monitors, traces
from governancekit.server.agents import AgentRegistry
from governancekit.server.audit import AuditLog
from governancekit.server.auth import Authenticator
from governancekit.server.state import ServerState

logger = logging.getLogger(__name__)


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
    agent_registry = AgentRegistry()
    app.state.gk = ServerState(
        auth=Authenticator(
            jwt_secret=jwt_secret, admin_secret=admin_secret, agents=agent_registry
        ),
        agents=agent_registry,
        registry=MonitorRegistry(),
        audit=AuditLog(),
    )

    app.include_router(auth.router)
    app.include_router(audit.router)
    app.include_router(agents.router)
    app.include_router(models.router)
    app.include_router(traces.router)
    app.include_router(monitors.router)

    # Let the frontend call the API.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:3000"],
        allow_methods=["*"],
        allow_headers=["*"],  # needed so the browser may send Authorization
    )

    return app


app = create_app()
