// The app's layout. Each feature lives in its own file in src/features/.

import { useState } from 'react'
import { AgentList } from './features/Agents'
import { AuthProvider, LoginForm, LogoutButton, useAuth } from './features/Auth'
import { ModelList } from './features/Models'
import { MonitorList } from './features/Monitors'
import { EndedTraceList } from './features/Traces'
import './App.css'

const TABS = {
  monitors: 'Trace monitors',
  ended: 'Ended traces',
  agents: 'Agents',
  models: 'Models',
}

type Tab = keyof typeof TABS

function App() {
  return (
    <AuthProvider>
      <Layout />
    </AuthProvider>
  )
}

function Layout() {
  const { token } = useAuth()
  const [tab, setTab] = useState<Tab>('monitors')

  return (
    <main className="app">
      <header className="app-header">
        <h1>Governance Kit</h1>
        {token && <LogoutButton />}
      </header>
      {token ? (
        <>
          <nav className="tabs" role="tablist">
            {(Object.keys(TABS) as Tab[]).map((key) => (
              <button
                key={key}
                type="button"
                role="tab"
                aria-selected={tab === key}
                onClick={() => setTab(key)}
              >
                {TABS[key]}
              </button>
            ))}
          </nav>
          {tab === 'monitors' && <MonitorList />}
          {tab === 'ended' && <EndedTraceList />}
          {tab === 'agents' && <AgentList />}
          {tab === 'models' && <ModelList />}
        </>
      ) : (
        <LoginForm />
      )}
    </main>
  )
}

export default App
