// Registered agents.

import { useCallback, useEffect, useState } from 'react'
import { ApiError, apiFetch, errorMessage } from '../api'
import { useSession } from './Auth'

/** Mirrors AgentInfo in src/governancekit/server/main.py. */
type AgentInfo = {
  agent_id: string
  agent_name: string
}

async function listAgents(token: string): Promise<AgentInfo[]> {
  const res = await apiFetch('/agents', token)
  const body: { agents: AgentInfo[] } = await res.json()
  return body.agents
}

export function AgentList() {
  const { token, logOut } = useSession()
  const [agents, setAgents] = useState<AgentInfo[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  // State is only set in the promise callbacks, after the request finishes
  const load = useCallback(
    () =>
      listAgents(token).then(
        (result) => {
          setAgents(result)
          setError(null)
        },
        (e) => {
          // Expired or invalid token: go back to the login form
          if (e instanceof ApiError && e.status === 401) logOut()
          else setError(errorMessage(e))
        },
      ),
    [token, logOut],
  )

  // Load when the component appears
  useEffect(() => {
    load()
  }, [load])

  return (
    <section className="card">
      <div className="card-header">
        <h2>Registered Agents</h2>
      </div>
      {error && <p className="error">{error}</p>}
      {agents === null && !error && <p>Loading…</p>}
      {agents?.length === 0 && <p>No agents registered yet.</p>}
      {agents && agents.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>ID</th>
            </tr>
          </thead>
          <tbody>
            {agents.map((agent) => (
              <tr key={agent.agent_id}>
                <td>{agent.agent_name}</td>
                <td>
                  <code>{agent.agent_id}</code>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}
