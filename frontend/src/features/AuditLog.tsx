// Audit log of what agents have checked, begun and finished.

import { useCallback, useEffect, useState } from 'react'
import { ApiError, apiFetch, errorMessage } from '../api'
import { useSession } from './Auth'

/** Mirrors Action in src/governancekit/server/audit.py. */
type AuditAction = 'start_trace' | 'end_trace' | 'check' | 'begin' | 'finish'

/** Mirrors Decision in src/governancekit/engine/decision.py. */
type Decision = 'allowed' | 'wait' | 'denied'

/** Mirrors ActivityStatus in src/governancekit/server/audit.py. */
type ActivityStatus = 'completed' | 'failed' | 'aborted'

/** Mirrors AuditEntry in src/governancekit/server/audit.py. Datetimes arrive as ISO 8601 strings. */
type AuditEntry = {
  received_at: string
  agent_id: string
  trace_id: string
  action: AuditAction
  activity: string | null // null for start/end trace
  event_timestamp: string | null // null for start/end trace
  decision: Decision | null // only set for check and begin
  instance_id: string | null // set for an allowed begin, and for finish
  status: ActivityStatus | null // only set for finish
  violations: string[] // for check, begin and end trace
}

/** The whole audit log, oldest entry first. */
async function listAuditLog(token: string): Promise<AuditEntry[]> {
  const res = await apiFetch('/audit', token)
  const body: { auditLog: AuditEntry[] } = await res.json()
  return body.auditLog
}

export function AuditLog() {
  const { token, logOut } = useSession()
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
