// Trace monitors: the engine's monitors of the running traces, one per trace.

import { useCallback, useEffect, useState } from 'react'
import { ApiError, apiFetch, errorMessage } from '../api'
import { formatTime } from '../format'
import { TraceAuditLog } from './Audit'
import { useSession } from './Auth'

/** Mirrors RunningActivity in src/governancekit/server/traces.py. */
type RunningActivity = {
  instance_id: string
  activity: string
  payload: Record<string, unknown>
  timestamp: string // when the activity began
}

/** Mirrors MonitorInfo in src/governancekit/server/monitors.py. */
type MonitorInfo = {
  trace_id: string // the monitored trace; also the monitor's ID
  model_id: string
  agent_ids: string[]
  started_at: string
  running: RunningActivity[] // begun but not finished
  violations: string[] // would be violated if the trace ended now
}

/** The monitors of all running traces, newest first. */
async function listMonitors(token: string): Promise<MonitorInfo[]> {
  const res = await apiFetch('/monitors', token)
  const body: { monitors: MonitorInfo[] } = await res.json()
  return body.monitors
}

export function MonitorList() {
  const { token, logOut } = useSession()
  const [monitors, setMonitors] = useState<MonitorInfo[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  // ID of the monitor whose details are shown
  const [selected, setSelected] = useState<string | null>(null)
  // Bumped on every load, so an open monitor fetches its log again too
  const [loadCount, setLoadCount] = useState(0)

  // State is only set in the promise callbacks, after the request finishes
  const load = useCallback(
    () =>
      listMonitors(token).then(
        (result) => {
          setMonitors(result)
          setError(null)
          setLoadCount((n) => n + 1)
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

  function toggle(traceId: string) {
    setSelected((current) => (current === traceId ? null : traceId))
  }

  return (
    <section className="card">
      <div className="card-header">
        <h2>Trace monitors</h2>
        <button type="button" className="secondary" onClick={load}>
          Refresh
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      {monitors === null && !error && <p>Loading…</p>}
      {monitors?.length === 0 && <p>No trace is running, so there are no monitors.</p>}
      {monitors && monitors.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Monitor</th>
              <th>Agents</th>
              <th>Running</th>
              <th>Unsatisfied</th>
            </tr>
          </thead>
          <tbody>
            {monitors.map((monitor) => (
              <MonitorRow
                key={monitor.trace_id}
                monitor={monitor}
                loadCount={loadCount}
                open={selected === monitor.trace_id}
                onToggle={() => toggle(monitor.trace_id)}
              />
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}

function MonitorRow({
  monitor,
  loadCount,
  open,
  onToggle,
}: {
  monitor: MonitorInfo
  loadCount: number
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
        <td>
          {/* The full ID is in the details */}
          <code>{monitor.trace_id.slice(0, 8)}</code>
        </td>
        <td>{monitor.agent_ids.length}</td>
        <td>{monitor.running.length}</td>
        <td>{monitor.violations.length}</td>
      </tr>
      {open && (
        <tr className="details">
          <td colSpan={4}>
            <dl>
              <dt>Monitor / trace</dt>
              <dd>
                <code>{monitor.trace_id}</code>
              </dd>
              <dt>Model</dt>
              <dd>
                <code>{monitor.model_id}</code>
              </dd>
              <dt>Agents</dt>
              <dd>
                <ul>
                  {monitor.agent_ids.map((id) => (
                    <li key={id}>
                      <code>{id}</code>
                    </li>
                  ))}
                </ul>
              </dd>
              <dt>Started</dt>
              <dd>{formatTime(monitor.started_at)}</dd>
              <dt>Running activities</dt>
              <dd>
                {monitor.running.length === 0 ? (
                  'None'
                ) : (
                  <ul>
                    {monitor.running.map((r) => (
                      <li key={r.instance_id}>
                        {r.activity}, began {formatTime(r.timestamp)}
                      </li>
                    ))}
                  </ul>
                )}
              </dd>
              <dt>Unsatisfied now</dt>
              <dd>
                {/* Not violations yet: they only count if the trace ends like this */}
                {monitor.violations.length === 0 ? (
                  'None'
                ) : (
                  <ul>
                    {monitor.violations.map((v) => (
                      <li key={v}>{v}</li>
                    ))}
                  </ul>
                )}
              </dd>
            </dl>
            <TraceAuditLog traceId={monitor.trace_id} loadCount={loadCount} />
          </td>
        </tr>
      )}
    </>
  )
}
