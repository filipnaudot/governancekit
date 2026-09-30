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


class Authenticator:
    """Issues and verifies JWTs, and keeps the known agents in memory.

    Attributes:
        agents: Hashed agent secrets, keyed by agent ID.
    """

    agents: dict[str, str]

    def __init__(self, jwt_secret: str, admin_secret: str):
        self._jwt_secret = jwt_secret
        self._admin_secret = admin_secret
        self._hasher = PasswordHash.recommended()
        self.agents = {}

    def register_agent(self) -> tuple[str, str]:
        """Register a new agent.

        Returns:
            A tuple (agent_id, secret). Only a hash of the secret is kept,
            so it cannot be shown again.
        """
        agent_id = str(uuid.uuid4())
        secret = secrets.token_urlsafe(32)
        self.agents[agent_id] = self._hasher.hash(secret)
        return agent_id, secret

    def authenticate(self, client_id: str, secret: str) -> Principal | None:
        """Return the principal for valid credentials, otherwise None."""
        if client_id == ADMIN_ID:
            if secrets.compare_digest(secret.encode(), self._admin_secret.encode()):
                return Principal(id=ADMIN_ID, role=Role.ADMIN)
            return None
        hashed = self.agents.get(client_id)
        if hashed is not None and self._hasher.verify(secret, hashed):
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
