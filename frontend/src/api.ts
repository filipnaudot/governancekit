// Client for the GovernanceKit API. Components call these functions instead
// of using fetch directly, so the URL, auth header and error handling live here.

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export type AgentInfo = {
  agent_id: string
  agent_name: string
}

/** Mirrors Action in api/audit.py. */
export type AuditAction = 'start_trace' | 'end_trace' | 'check' | 'commit'

/** Mirrors AuditEntry in api/audit.py. Datetimes arrive as ISO 8601 strings. */
export type AuditEntry = {
  received_at: string
  agent_id: string
  trace_id: string
  action: AuditAction
  activity: string | null // null for start/end trace
  event_timestamp: string | null // null for start/end trace
  allowed: boolean | null // only set for check
  violations: string[] // for check and end trace
}

/** An error response from the API, with its HTTP status. */
export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function throwIfNotOk(res: Response): Promise<Response> {
  if (res.ok) return res
  // FastAPI puts the error message in "detail"
  const body = await res.json().catch(() => ({}))
  throw new ApiError(res.status, body.detail ?? res.statusText)
}

/**
 * Exchange an ID and secret for a bearer token.
 * /token expects form data, not JSON (OAuth2 standard).
 */
export async function login(id: string, secret: string): Promise<string> {
  const res = await fetch(`${API_URL}/token`, {
    method: 'POST',
    body: new URLSearchParams({ username: id, password: secret }),
  })
  await throwIfNotOk(res)
  const body: { access_token: string } = await res.json()
  return body.access_token
}

/** fetch with the bearer token and JSON content type set. */
export async function apiFetch(
  path: string,
  token: string,
  init: RequestInit = {},
): Promise<Response> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      ...init.headers,
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  })
  return throwIfNotOk(res)
}

export async function listAgents(token: string): Promise<AgentInfo[]> {
  const res = await apiFetch('/agents', token)
  const body: { agents: AgentInfo[] } = await res.json()
  return body.agents
}

/** The whole audit log, oldest entry first. */
export async function listAuditLog(token: string): Promise<AuditEntry[]> {
  const res = await apiFetch('/audit', token)
  const body: { auditLog: AuditEntry[] } = await res.json()
  return body.auditLog
}
