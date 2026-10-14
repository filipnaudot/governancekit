"""
Agent management endpoints for the GovernanceKit web server.

Admins register agents and list the known ones. Each agent gets an ID and a
secret it uses to log in at /token.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from governancekit.server.auth import Agent, require_admin
from governancekit.server.state import ServerState, get_state

router = APIRouter(tags=["management"], dependencies=[Depends(require_admin)])

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
        agents=[AgentInfo.of(agent) for agent in state.auth.agents.values()]
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
    agent, secret = state.auth.register_agent(name=body.agent_name)
    return RegisterAgentResponse(agent_info=AgentInfo.of(agent), secret=secret)
