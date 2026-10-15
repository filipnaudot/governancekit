"""
Agent management endpoints for the GovernanceKit web server.

Admins register agents and list the known ones. Each agent gets an ID and a
secret it uses to log in at /token.
"""

import secrets
import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, Depends, status
from pwdlib import PasswordHash
from pydantic import BaseModel, Field

from governancekit.server.auth import require_admin
from governancekit.server.state import ServerState, get_state

router = APIRouter(tags=["management"], dependencies=[Depends(require_admin)])


# TODO Maybe the agent should have a record of what active traces it is working on. Maybe it can't be frozen then. 
@dataclass(frozen=True)
class Agent:
    """A registered agent as stored by the server. Never sent to clients."""

    id: str
    name: str
    secret_hash: str


class AgentRegistry:
    """The registered agents, kept in memory.

    Attributes:
        agents: Registered agents, keyed by agent ID.
    """

    agents: dict[str, Agent]

    def __init__(self):
        self._hasher = PasswordHash.recommended()
        self.agents = {}

    def register(self, name: str) -> tuple[Agent, str]:
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

    def verify_secret(self, agent_id: str, secret: str) -> bool:
        """Whether agent_id is registered and secret is its secret."""
        agent = self.agents.get(agent_id)
        return agent is not None and self._hasher.verify(secret, agent.secret_hash)


# ---------- Request / response schemas ----------


class RegisterAgentRequest(BaseModel):
    """
    MVP class for agent registry.
    TODO Find out what information is interesting about an agent.
    """

    agent_name: str


class AgentInfo(BaseModel):
    """
    Public information about an agent. Never includes its secret or hash.
    """

    agent_id: str
    agent_name: str

    @classmethod
    def of(cls, agent: Agent) -> "AgentInfo":
        """
        The class method chooses which fields of AgentInfo that is passed to the client.
        """
        return cls(agent_id=agent.id, agent_name=agent.name)


class RegisterAgentResponse(BaseModel):
    agent_info: AgentInfo
    secret: str = Field(description="Shown only once; the server keeps a hash")


class AgentListResponse(BaseModel):
    agents: list[AgentInfo]


# ---------- Endpoints ----------


@router.get("/agents")
def return_known_agents(
    state: Annotated[ServerState, Depends(get_state)],
) -> AgentListResponse:
    """
    Admin endpoint. Returns the known agents from the server's memory.
    The function could be extended to return more properties about the agents. Do so by changing the .of method of AgentInfo.
    """
    return AgentListResponse(
        agents=[AgentInfo.of(agent) for agent in state.agents.agents.values()]
    )


@router.post("/agents", status_code=status.HTTP_201_CREATED)
def register_agent(
    body: RegisterAgentRequest,
    state: Annotated[ServerState, Depends(get_state)],
) -> RegisterAgentResponse:
    """
    Register an agent and return its ID and secret.
    """
    # The server creates the ID and secret
    agent, secret = state.agents.register(name=body.agent_name)
    return RegisterAgentResponse(agent_info=AgentInfo.of(agent), secret=secret)
