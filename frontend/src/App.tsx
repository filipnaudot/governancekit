import { useCallback, useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { ApiError, listAgents, login } from './api'
import type { AgentInfo } from './api'
import './App.css'

const TOKEN_KEY = 'gk-token'

// sessionStorage keeps you logged in across reloads until the tab is closed.
// It can throw (e.g. blocked storage), so the app also works without it.
function loadToken(): string | null {
  try {
    return sessionStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

function saveToken(token: string | null) {
  try {
    if (token) sessionStorage.setItem(TOKEN_KEY, token)
    else sessionStorage.removeItem(TOKEN_KEY)
  } catch {
    // Ignore: the token is still kept in React state
  }
}

function App() {
  const [token, setToken] = useState<string | null>(loadToken)

  function handleLogin(newToken: string) {
    saveToken(newToken)
    setToken(newToken)
  }

  // Stable identity, so AgentList does not reload when App re-renders
  const handleLogout = useCallback(() => {
    saveToken(null)
    setToken(null)
  }, [])

  return (
    <main className="app">
      <header className="app-header">
        <h1>GovernanceKit</h1>
        {token && (
          <button type="button" className="secondary" onClick={handleLogout}>
            Log out
          </button>
        )}
      </header>
      {token ? (
        <AgentList token={token} onUnauthorized={handleLogout} />
      ) : (
        <LoginForm onLogin={handleLogin} />
      )}
    </main>
  )
}

function LoginForm({ onLogin }: { onLogin: (token: string) => void }) {
  const [id, setId] = useState('admin')
  const [secret, setSecret] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      onLogin(await login(id, secret))
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="card" onSubmit={handleSubmit}>
      <h2>Log in</h2>
      <label>
        ID
        <input value={id} onChange={(e) => setId(e.target.value)} required />
      </label>
      <label>
        Secret
        <input
          type="password"
          value={secret}
          onChange={(e) => setSecret(e.target.value)}
          required
          autoFocus
        />
      </label>
      {error && <p className="error">{error}</p>}
      <button type="submit" disabled={busy}>
        {busy ? 'Logging in…' : 'Log in'}
      </button>
    </form>
  )
}

function AgentList({
  token,
  onUnauthorized,
}: {
  token: string
  onUnauthorized: () => void
}) {
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
          if (e instanceof ApiError && e.status === 401) onUnauthorized()
          else setError(errorMessage(e))
        },
      ),
    [token, onUnauthorized],
  )

  // Load when the component appears
  useEffect(() => {
    load()
  }, [load])

  return (
    <section className="card">
      <div className="card-header">
        <h2>Known agents</h2>
        <button type="button" className="secondary" onClick={load}>
          Refresh
        </button>
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

function errorMessage(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.status === 403) return 'Only admins can see the agents.'
    return e.message
  }
  // fetch itself failed: server down, or CORS blocked the request
  return 'Cannot reach the API. Is it running on http://localhost:8000?'
}

export default App
