// Shared client for the GovernanceKit API. Each feature in src/features/ has
// its own API calls; they use apiFetch, so the URL, auth header and error
// handling live here.

export const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

/** An error response from the API, with its HTTP status. */
export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export async function throwIfNotOk(res: Response): Promise<Response> {
  if (res.ok) return res
  // FastAPI puts the error message in "detail"
  const body = await res.json().catch(() => ({}))
  throw new ApiError(res.status, body.detail ?? res.statusText)
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

/** A message to show the user for a failed request. */
export function errorMessage(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.status === 403) return 'Requires an admin login.'
    return e.message
  }
  // fetch itself failed: server down, or CORS blocked the request
  return `Cannot reach the API. Is it running on ${API_URL}?`
}
