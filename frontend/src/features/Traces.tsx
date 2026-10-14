// Ended traces, each with its final verdict and audit log. Running traces are
// shown through their monitors, in Monitors.tsx.

import { useCallback, useEffect, useState } from 'react'
import { ApiError, apiFetch, errorMessage } from '../api'
import { formatTime } from '../format'
import { TraceAuditLog } from './Audit'
import { useSession } from './Auth'

/** Mirrors TraceSummary in src/governancekit/server/traces.py, for an ended trace. */
type EndedTrace = {
  trace_id: string
  model_id: string
  agent_ids: string[]
  started_at: string
  ended_at: string
  violations: string[] // the final verdict
}

/** Ended traces, newest first. */
async function listEndedTraces(token: string): Promise<EndedTrace[]> {
  const res = await apiFetch('/traces?ended=true', token)
  const body: { traces: EndedTrace[] } = await res.json()
  return body.traces
}

export function EndedTraceList() {
  const { token, logOut } = useSession()
  const [traces, setTraces] = useState<EndedTrace[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  // ID of the trace whose details are shown
  const [selected, setSelected] = useState<string | null>(null)

  // State is only set in the promise callbacks, after the request finishes
  const load = useCallback(
    () =>
      listEndedTraces(token).then(
        (result) => {
          setTraces(result)
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

  function toggle(traceId: string) {
    setSelected((current) => (current === traceId ? null : traceId))
  }

  return (
    <section className="card">
      <div className="card-header">
        <h2>Ended Traces</h2>
        <button type="button" className="secondary" onClick={load}>
          Refresh
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      {traces === null && !error && <p>Loading…</p>}
      {traces?.length === 0 && <p>No trace has ended yet.</p>}
      {traces && traces.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Trace</th>
              <th>Agents</th>
              <th>Ended</th>
              <th>Result</th>
            </tr>
          </thead>
          <tbody>
            {traces.map((trace) => (
              <TraceRow
                key={trace.trace_id}
                trace={trace}
                open={selected === trace.trace_id}
                onToggle={() => toggle(trace.trace_id)}
              />
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}

function TraceRow({
  trace,
  open,
  onToggle,
}: {
  trace: EndedTrace
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
          <code>{trace.trace_id.slice(0, 8)}</code>
        </td>
        <td>{trace.agent_ids.length}</td>
        <td>{formatTime(trace.ended_at)}</td>
        <td>{verdict(trace.violations)}</td>
      </tr>
      {open && (
        <tr className="details">
          <td colSpan={4}>
            <dl>
              <dt>Trace</dt>
              <dd>
                <code>{trace.trace_id}</code>
              </dd>
              <dt>Model</dt>
              <dd>
                <code>{trace.model_id}</code>
              </dd>
              <dt>Agents</dt>
              <dd>
                <ul>
                  {trace.agent_ids.map((id) => (
                    <li key={id}>
                      <code>{id}</code>
                    </li>
                  ))}
                </ul>
              </dd>
              <dt>Started</dt>
              <dd>{formatTime(trace.started_at)}</dd>
              <dt>Ended</dt>
              <dd>{formatTime(trace.ended_at)}</dd>
              {trace.violations.length > 0 && (
                <>
                  <dt>Violations</dt>
                  <dd>
                    <ul>
                      {trace.violations.map((v) => (
                        <li key={v}>{v}</li>
                      ))}
                    </ul>
                  </dd>
                </>
              )}
            </dl>
            {/* An ended trace's log no longer changes */}
            <TraceAuditLog traceId={trace.trace_id} loadCount={0} />
          </td>
        </tr>
      )}
    </>
  )
}

function verdict(violations: string[]): string {
  return violations.length === 0 ? 'Conformant' : `${violations.length} violation(s)`
}
