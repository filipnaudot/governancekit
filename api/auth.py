"""
Authentication for the GovernanceKit web server.

Admins manage models, traces and agents. Agents can only check and commit
events on traces assigned to them. Both log in at /token with an ID and a
secret and send the returned JWT as a bearer token.
"""

import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

import jwt
from pwdlib import PasswordHash

ADMIN_ID = "admin"
ALGORITHM = "HS256"
TOKEN_LIFETIME = timedelta(minutes=15)


class Role(StrEnum):
    ADMIN = "admin"
    AGENT = "agent"


@dataclass(frozen=True)
class Principal:
    """The authenticated caller of a request."""
    id: str
    role: Role


@dataclass(frozen=True)
class Agent:
    """A registered agent as stored by the server. Never sent to clients."""

    id: str
    name: str
    secret_hash: str


class Authenticator:
    """Issues and verifies JWTs, and keeps the known agents in memory.

    Attributes:
        agents: Registered agents, keyed by agent ID.
    """

    agents: dict[str, Agent]

    def __init__(self, jwt_secret: str, admin_secret: str):
        self._jwt_secret = jwt_secret
        self._admin_secret = admin_secret
        self._hasher = PasswordHash.recommended()
        self.agents = {}

    def register_agent(self, name: str) -> tuple[Agent, str]:
        """Register a new agent.

        Args:
            name: Human-readable name of the agent. Does not need to be unique.

        Returns:
            A tuple (agent, secret). Only a hash of the secret is kept,
            so it cannot be shown again.
        """
        secret = secrets.token_urlsafe(32)
        agent = Agent(
            id=str(uuid.uuid4()), name=name, secret_hash=self._hasher.hash(secret)
        )
        self.agents[agent.id] = agent
        return agent, secret

    def authenticate(self, client_id: str, secret: str) -> Principal | None:
        """Return the principal for valid credentials, otherwise None."""
        if client_id == ADMIN_ID:
            if secrets.compare_digest(secret.encode(), self._admin_secret.encode()):
                return Principal(id=ADMIN_ID, role=Role.ADMIN)
            return None
        agent = self.agents.get(client_id)
        if agent is not None and self._hasher.verify(secret, agent.secret_hash):
            return Principal(id=client_id, role=Role.AGENT)
        return None

    def create_token(self, principal: Principal) -> str:
        claims = {
            "sub": principal.id,
            "role": principal.role.value,
            "exp": datetime.now(UTC) + TOKEN_LIFETIME,
        }
        return jwt.encode(claims, self._jwt_secret, algorithm=ALGORITHM)

    def verify_token(self, token: str) -> Principal:
        """Decode a token issued by create_token.

        Raises:
            jwt.InvalidTokenError: If the token is malformed, expired or not
                                   signed with this server's secret.
        """
        claims = jwt.decode(
            token,
            self._jwt_secret,
            algorithms=[ALGORITHM],
            options={"require": ["sub", "role", "exp"]},
        )
        return Principal(id=claims["sub"], role=Role(claims["role"]))
