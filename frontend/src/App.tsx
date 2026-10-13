// The app's layout. Each feature lives in its own file in src/features/.

import { AgentList } from './features/Agents'
import { AuditLog } from './features/AuditLog'
import { AuthProvider, LoginForm, LogoutButton, useAuth } from './features/Auth'
import { ModelList } from './features/Models'
import './App.css'

function App() {
  return (
    <AuthProvider>
      <Layout />
    </AuthProvider>
  )
}

function Layout() {
  const { token } = useAuth()

  return (
    <main className="app">
      <header className="app-header">
        <h1>Governance Kit</h1>
        {token && <LogoutButton />}
      </header>
      {token ? (
        <>
          <AuditLog />
          <AgentList />
          <ModelList />
        </>
      ) : (
        <LoginForm />
      )}
    </main>
  )
}

export default App
