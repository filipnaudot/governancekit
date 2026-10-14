// Logging in and out. AuthProvider holds the token; components read it with
// useAuth (logged in or not) or useSession (only rendered when logged in).

import { createContext, useCallback, useContext, useMemo, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { API_URL, errorMessage, throwIfNotOk } from '../api'

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

/**
 * Exchange an ID and secret for a bearer token.
 * /token expects form data, not JSON (OAuth2 standard).
 */
async function login(id: string, secret: string): Promise<string> {
  const res = await fetch(`${API_URL}/token`, {
    method: 'POST',
    body: new URLSearchParams({ username: id, password: secret }),
  })
  await throwIfNotOk(res)
  const body: { access_token: string } = await res.json()
  return body.access_token
}

type Auth = {
  token: string | null
  logIn: (token: string) => void
  logOut: () => void
}

const AuthContext = createContext<Auth | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(loadToken)

  const logIn = useCallback((newToken: string) => {
    saveToken(newToken)
    setToken(newToken)
  }, [])

  // Stable, so components can list it as an effect dependency
  const logOut = useCallback(() => {
    saveToken(null)
    setToken(null)
  }, [])

  const auth = useMemo(() => ({ token, logIn, logOut }), [token, logIn, logOut])
  return <AuthContext.Provider value={auth}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): Auth {
  const auth = useContext(AuthContext)
  if (!auth) throw new Error('useAuth must be used inside AuthProvider')
  return auth
}

/** For components that are only shown when logged in. */
// eslint-disable-next-line react-refresh/only-export-components
export function useSession(): { token: string; logOut: () => void } {
  const { token, logOut } = useAuth()
  if (!token) throw new Error('useSession requires a logged in user')
  return { token, logOut }
}

export function LoginForm() {
  const { logIn } = useAuth()
  const [id, setId] = useState('')
  const [secret, setSecret] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      logIn(await login(id, secret))
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

export function LogoutButton() {
  const { logOut } = useAuth()
  return (
    <button type="button" className="secondary" onClick={logOut}>
      Log out
    </button>
  )
}
