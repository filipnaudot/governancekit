import { useCallback, useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { ApiError, listAgents, listAuditLog, login } from './api'
import type {
  ActivityStatus,
  AgentInfo,
  AuditAction,
  AuditEntry,
  Decision,
} from './api'
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

  function handleLogout() {
    saveToken(null)
    setToken(null)
  }

  return (
    <main className="app">
      <header className="app-header">
        <h1>Governance Kit</h1>
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

      {token && <AuditLog token={token} onUnauthorized={handleLogout} />}
    </main>
  )
}

function LoginForm({ onLogin }: { onLogin: (token: string) => void }) {
  const [id, setId] = useState('')
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
        <h2>Registered Agents</h2>
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


function AuditLog({
  token,
  onUnauthorized,
}: {
  token: string
  onUnauthorized: () => void
}) {
  const [entries, setEntries] = useState<AuditEntry[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  // Index (in the server's list) of the entry whose details are shown
  const [selected, setSelected] = useState<number | null>(null)

  // State is only set in the promise callbacks, after the request finishes
  const load = useCallback(
    () =>
      listAuditLog(token).then(
        (result) => {
          setEntries(result)
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

  function toggle(index: number) {
    setSelected((current) => (current === index ? null : index))
  }

  return (
    <section className="card">
      <div className="card-header">
        <h2>Agent Audit Log</h2>
        <button type="button" className="secondary" onClick={load}>
          Refresh
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      {entries === null && !error && <p>Loading…</p>}
      {entries?.length === 0 && <p>Nothing recorded yet.</p>}
      {entries && entries.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Received</th>
              <th>Action</th>
              <th>Activity</th>
              <th>Result</th>
            </tr>
          </thead>
          <tbody>
            {/* Newest first. The log is append-only, so the index is a stable key. */}
            {entries
              .map((entry, index) => ({ entry, index }))
              .reverse()
              .map(({ entry, index }) => (
                <AuditRow
                  key={index}
                  entry={entry}
                  open={selected === index}
                  onToggle={() => toggle(index)}
                />
              ))}
          </tbody>
        </table>
      )}
    </section>
  )
}

function AuditRow({
  entry,
  open,
  onToggle,
}: {
  entry: AuditEntry
  open: boolean
  onToggle: () => void
}) {
  return (
    <>
      <tr
        className="clickable"
        tabIndex={0}
        aria-expanded={open}
        onClick={onToggle}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            onToggle()
          }
        }}
      >
        <td>{formatTime(entry.received_at)}</td>
        <td>{ACTION_LABELS[entry.action]}</td>
        <td>{entry.activity ?? '—'}</td>
        <td>{auditResult(entry)}</td>
      </tr>
      {open && (
        <tr className="details">
          <td colSpan={4}>
            <dl>
              <dt>Agent</dt>
              <dd>
                <code>{entry.agent_id}</code>
              </dd>
              <dt>Trace</dt>
              <dd>
                <code>{entry.trace_id}</code>
              </dd>
              <dt>Received at</dt>
              <dd>{entry.received_at}</dd>
              {entry.event_timestamp && (
                <>
                  <dt>Event timestamp</dt>
                  <dd>{entry.event_timestamp}</dd>
                </>
              )}
              {entry.decision && (
                <>
                  <dt>Decision</dt>
                  <dd>{DECISION_LABELS[entry.decision]}</dd>
                </>
              )}
              {entry.instance_id && (
                <>
                  <dt>Instance</dt>
                  <dd>
                    <code>{entry.instance_id}</code>
                  </dd>
                </>
              )}
              {entry.status && (
                <>
                  <dt>Status</dt>
                  <dd>{STATUS_LABELS[entry.status]}</dd>
                </>
              )}
              {entry.action !== 'start_trace' && entry.action !== 'finish' && (
                <>
                  <dt>Violations</dt>
                  <dd>
                    {entry.violations.length === 0 ? (
                      'None'
                    ) : (
                      <ul>
                        {entry.violations.map((v) => (
                          <li key={v}>{v}</li>
                        ))}
                      </ul>
                    )}
                  </dd>
                </>
              )}
            </dl>
          </td>
        </tr>
      )}
    </>
  )
}

const ACTION_LABELS: Record<AuditAction, string> = {
  start_trace: 'Start trace',
  end_trace: 'End trace',
  check: 'Check',
  begin: 'Begin',
  finish: 'Finish',
}

const DECISION_LABELS: Record<Decision, string> = {
  allowed: 'Allowed',
  wait: 'Wait',
  denied: 'Denied',
}

const STATUS_LABELS: Record<ActivityStatus, string> = {
  completed: 'Completed',
  failed: 'Failed',
  aborted: 'Aborted',
}

/** One-word summary for the table; the details row has the rest. */
function auditResult(entry: AuditEntry): string {
  if (entry.decision) return DECISION_LABELS[entry.decision]
  if (entry.status) return STATUS_LABELS[entry.status]
  if (entry.action === 'end_trace') {
    return entry.violations.length === 0
      ? 'Conformant'
      : `${entry.violations.length} violation(s)`
  }
  return '—'
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString()
}

function errorMessage(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.status === 403) return 'Requires an admin login.'
    return e.message
  }
  // fetch itself failed: server down, or CORS blocked the request
  return 'Cannot reach the API. Is it running on http://localhost:8000?'
}

export default App
