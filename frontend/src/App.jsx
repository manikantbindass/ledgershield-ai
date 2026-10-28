import { useEffect, useState } from 'react'
import LiveProvider from './LiveProvider'
import { useDashboard } from './lib/context'
import { routeFromHash } from './lib/utils'
import { Badge, Empty, Icon, Loading } from './components'
import { BlockchainExplorer, NetworkExplorer, Overview, SecurityCenter } from './pages/Observe'
import { HealingCenter, SettingsAudit, SimulationLab, TrustManagement } from './pages/Operations'
import { ExperimentReports, RLLab } from './pages/Research'

const pages = [
  ['overview', 'Overview', Overview, 'A measured view of network resilience.'],
  [
    'network',
    'Network Explorer',
    NetworkExplorer,
    'Inspect participants, connectivity and validator state.',
  ],
  [
    'blockchain',
    'Blockchain Explorer',
    BlockchainExplorer,
    'Follow signed transfers from intent to canonical execution.',
  ],
  [
    'security',
    'Security Center',
    SecurityCenter,
    'Investigate anomaly indicators and their supporting evidence.',
  ],
  [
    'trust',
    'Trust Management',
    TrustManagement,
    'Understand every consequential reputation change.',
  ],
  [
    'healing',
    'Self-Healing Center',
    HealingCenter,
    'Trace proposals, safety decisions and measured recovery outcomes.',
  ],
  ['rl', 'RL Lab', RLLab, 'Inspect recorded learning and evaluate policy assumptions.'],
  [
    'simulation',
    'Simulation Lab',
    SimulationLab,
    'Design bounded, reversible local fault experiments.',
  ],
  [
    'reports',
    'Experiment Reports',
    ExperimentReports,
    'Compare reproducible results and export the evidence.',
  ],
  [
    'settings',
    'Settings & Audit',
    SettingsAudit,
    'Manage local access, safe settings and operational diagnostics.',
  ],
]

function Dashboard() {
  const [route, setRoute] = useState(() => routeFromHash(location.hash))
  const [menu, setMenu] = useState(false)
  const [theme, setTheme] = useState(() => {
    try {
      return localStorage.getItem('ledgershield-theme') === 'light' ? 'light' : 'dark'
    } catch {
      return 'dark'
    }
  })
  const { snapshot, connection, lastSeen, role, notice, setNotice, busy, refresh } = useDashboard()
  useEffect(() => {
    const navigate = () => {
      setRoute(routeFromHash(location.hash))
      setMenu(false)
    }
    window.addEventListener('hashchange', navigate)
    return () => window.removeEventListener('hashchange', navigate)
  }, [])
  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try {
      localStorage.setItem('ledgershield-theme', theme)
    } catch {
      /* Storage is optional. */
    }
  }, [theme])
  const current = pages.find((page) => page[0] === route)
  const Page = current?.[2]
  return (
    <div className="app-shell">
      <a
        href="#main-content"
        className="skip-link"
        onClick={(event) => {
          event.preventDefault()
          document.getElementById('main-content')?.focus()
        }}
      >
        Skip to content
      </a>
      <aside className={`sidebar ${menu ? 'menu-open' : ''}`}>
        <a className="brand" href="#/overview">
          <span className="brand-mark">
            <Icon name="security" size={27} />
          </span>
          <span>
            LedgerShield<span className="brand-dot">.</span>
          </span>
        </a>
        <div className="workspace-label">
          <span className="signal-marker" />
          RESEARCH WORKSPACE <small>01</small>
        </div>
        <nav aria-label="Dashboard pages">
          {pages.map(([id, title], i) => (
            <a
              href={`#/${id}`}
              key={id}
              aria-label={title}
              aria-current={route === id ? 'page' : undefined}
            >
              <Icon name={id} />
              <span>{title}</span>
              {id === 'security' && !!snapshot?.metrics.anomalies && (
                <small>{snapshot.metrics.anomalies}</small>
              )}
              {i === 0 && <span className="nav-indicator" />}
            </a>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <Badge tone="good">Controlled simulation</Badge>
          <p>
            Explain the evidence.
            <br />
            Measure the recovery.
          </p>
          <small>
            Local research prototype
            <br />
            No real funds or P2P deployment
          </small>
          <a href="http://127.0.0.1:8000/docs" target="_blank" rel="noreferrer">
            API reference ↗
          </a>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div className="breadcrumbs">
            <button
              className="icon-button mobile-menu"
              aria-expanded={menu}
              aria-label={menu ? 'Close navigation' : 'Open navigation'}
              onClick={() => setMenu(!menu)}
            >
              <Icon name="menu" />
            </button>
            <span>WORKSPACE</span>
            <span>/</span>
            <strong>{current?.[1] || 'Unknown page'}</strong>
          </div>
          <div className="top-actions">
            <span className={`connection ${connection}`}>
              <i />
              {connection === 'live'
                ? 'Live simulator'
                : connection === 'connecting'
                  ? 'Connecting'
                  : 'Offline'}
            </span>
            <button
              className="icon-button"
              aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
              title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
              onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
            >
              <Icon name="sun" />
            </button>
            <a className="access-button" href="#/settings" aria-label="Open access settings">
              <span>{role.charAt(0).toUpperCase()}</span>
              <span>{role === 'viewer' ? 'Read-only access' : `${role} access`}</span>
            </a>
          </div>
        </header>
        <main id="main-content" tabIndex="-1">
          <div className="page-title">
            <div>
              <div className="eyebrow">
                LEDGERSHIELD /{' '}
                {String(
                  Math.max(
                    0,
                    pages.findIndex((p) => p[0] === route),
                  ) + 1,
                ).padStart(2, '0')}
              </div>
              <h1>{current?.[1] || 'Page not found'}</h1>
              <p>{current?.[3] || 'Choose a page from the navigation to continue.'}</p>
            </div>
            <div className="page-actions">
              <Badge tone={snapshot?.running ? 'good' : ''}>
                {snapshot?.running ? 'Simulation running' : 'Simulation paused'}
              </Badge>
              <button
                disabled={busy}
                className="icon-button"
                aria-label="Refresh server data"
                title="Refresh server data"
                onClick={refresh}
              >
                <Icon name="refresh" />
              </button>
            </div>
          </div>
          {connection !== 'live' && (
            <div className="notice warning" role="status">
              <strong>
                {connection === 'connecting'
                  ? 'Connecting to the local API.'
                  : 'Live connection lost. Reconnecting automatically.'}
              </strong>{' '}
              {snapshot
                ? `Showing the last received simulator snapshot, tick ${snapshot.metrics.simulated_seconds}${lastSeen ? `, observed at ${new Date(lastSeen).toLocaleTimeString()}` : ''}. Controls are disabled until live updates resume.`
                : 'Start the local backend on port 8000. No measurements are available yet.'}
            </div>
          )}
          {notice && (
            <div
              className={`notice ${notice.type}`}
              role={notice.type === 'error' ? 'alert' : 'status'}
            >
              <div>
                <strong>{notice.message}</strong>
                {notice.request_id && <small>Request ID: {notice.request_id}</small>}
              </div>
              <button aria-label="Dismiss notification" onClick={() => setNotice(null)}>
                Dismiss
              </button>
            </div>
          )}
          {busy && (
            <div className="working" role="status">
              <span className="spinner" />
              Processing authorized request…
            </div>
          )}
          {role === 'viewer' && snapshot && (
            <div className="access-note">
              <Icon name="security" size={15} />
              <span>
                Read-only research access. <a href="#/settings">Verify a local API token</a> to
                operate the simulator.
              </span>
            </div>
          )}
          {!Page ? (
            <Empty title="Unknown dashboard page">
              <a className="text-link" href="#/overview">
                Return to Overview
              </a>
            </Empty>
          ) : snapshot ? (
            <Page key={`${route}:${snapshot.instance_id}`} />
          ) : connection === 'connecting' ? (
            <Loading />
          ) : (
            <Empty title="No simulator data available">
              Cached or generated values are never substituted for missing measurements. Use Refresh
              server data to retry while the connection recovers.
            </Empty>
          )}
          <footer>
            <span>LedgerShield · Local research simulator · In-memory state</span>
            <span>
              Simulated time <strong>{snapshot?.metrics.simulated_seconds ?? '—'} ticks</strong> ·
              API v1
            </span>
          </footer>
        </main>
      </div>
    </div>
  )
}
export default function App() {
  return (
    <LiveProvider>
      <Dashboard />
    </LiveProvider>
  )
}
