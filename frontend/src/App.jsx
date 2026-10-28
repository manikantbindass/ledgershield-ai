import { useEffect, useState } from 'react'

const fmt = value => Number(value ?? 0).toFixed(1)

export default function App() {
  const [state, setState] = useState(null)
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [token, setToken] = useState('')

  useEffect(() => {
    let ws, retry, cancelled = false
    function connect() {
      if (cancelled) return
      ws = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/api/v1/ws`)
      ws.onopen = () => setConnected(true)
      ws.onmessage = event => {
        try {
          const message = JSON.parse(event.data)
          if (message.type === 'snapshot') setState(message.data)
        }
        catch { setError('Received an invalid simulator update.') }
      }
      ws.onclose = () => {
        setConnected(false)
        if (!cancelled) retry = setTimeout(connect, 2000)
      }
      ws.onerror = () => ws.close()
    }
    connect()
    return () => { cancelled = true; clearTimeout(retry); ws?.close() }
  }, [])

  async function post(path, body = {}) {
    setBusy(true); setError('')
    try {
      const response = await fetch(`/api/v1${path}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` }, body: JSON.stringify(body),
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.error?.detail ?? 'Request failed')
      const fresh = await fetch('/api/v1/network/state')
      if (!fresh.ok) throw new Error('Could not refresh simulator state')
      setState(await fresh.json())
    } catch (err) { setError(err.message) }
    finally { setBusy(false) }
  }

  const metrics = state?.metrics ?? {}
  return (
    <div className="shell">
      <aside className="sidebar">
        <a href="#overview" className="brand"><span className="shield">◇</span> LedgerShield<span className="brand-dot">.</span></a>
        <p className="eyebrow">RESILIENCE LAB / 01</p>
        <nav aria-label="Dashboard navigation">
          <a className="selected" href="#overview">◈ <span>Overview</span></a>
          <a href="#network">⌘ <span>Network nodes</span></a>
          <a href="#alerts">⚑ <span>Evidence & alerts</span></a>
          <a href="#recovery">↻ <span>Recovery journal</span></a>
          <a href="http://127.0.0.1:8000/docs" target="_blank" rel="noreferrer">↗ <span>API reference</span></a>
        </nav>
        <div className="lab-note"><span className="status-dot" /> LOCAL SIMULATOR<p>Reproducible experiments.<br />Explainable decisions.</p><small>Educational prototype · no real funds</small></div>
      </aside>
      <main id="overview">
        <header className="topbar"><span>WORKSPACE <b>/ Network observatory</b></span><span className={`connection ${connected ? 'live' : ''}`}><i />{connected ? 'Live telemetry' : 'Reconnecting…'}</span></header>
        <div className="auth-bar"><label>Local API access <input type="password" autoComplete="off" aria-label="Operator or admin API token" placeholder="Paste operator or admin token" value={token} onChange={event => setToken(event.target.value)} /></label><span>Token stays in this tab’s memory. Admin access is needed for approvals, modes and reset.</span></div>
        <section className="intro"><div><p className="eyebrow">MONITOR. UNDERSTAND. RECOVER.</p><h1>A clearer view of<br />network resilience<span>.</span></h1><p>Signed transfers, consensus evidence, and controlled recovery.<br />Every number comes from the local simulator.</p></div><div className="orbit" aria-hidden="true"><div className="orbit-ring" /><div className="orbit-ring inner" /><span className="core-shield">◇</span><i className="satellite s1" /><i className="satellite s2" /><i className="satellite s3" /></div></section>
        {error && <div role="alert" className="error">{error}</div>}
        {!state ? <div className="panel empty">Connecting to the LedgerShield API on port 8000…</div> : <>
          <section className="stats" aria-label="Simulator metrics">
            <Metric label="BLOCK HEIGHT" value={metrics.height} suffix="blocks" detail={`View ${metrics.view} · fixed quorum ${metrics.quorum}`} />
            <Metric label="TRANSACTION THROUGHPUT" value={fmt(metrics.throughput)} suffix="tx / sim s" detail={`${metrics.accepted} accepted · ${metrics.rejected} rejected`} />
            <Metric label="MESSAGE LATENCY" value={fmt(metrics.message_latency_ms)} suffix="ms" detail={`${metrics.timeouts} transport timeouts`} />
            <Metric label="RECOVERY OUTCOMES" value={metrics.recovery_successes} suffix="verified" detail={`${metrics.recovery_attempts} attempted · ${metrics.recovery_failures} rolled back`} />
          </section>
          <section className="controls panel"><div><p className="eyebrow">EXPERIMENT CONTROLS</p><p className="muted">Changes affect this local simulation only.</p></div><div className="actions">
            <button disabled={busy || !token} onClick={() => post('/simulation/transaction')}>+ Signed demo transfer</button>
            <button disabled={busy || !token} onClick={() => post('/simulation/step')}>Advance round ↗</button>
            <button disabled={busy || !token} className="subtle" onClick={() => post('/simulation/reset')}>Reset</button>
          </div></section>
          <section id="network"><div className="section-heading"><h2>Network participants <span>{state.nodes.length}</span></h2><p>Validator membership stays fixed during recovery</p></div><div className="nodes">{state.nodes.map(node => <article className={`panel node ${node.quarantined ? 'isolated' : ''}`} key={node.id}>
            <div className="node-head"><span className="node-icon">⬡</span><span className={`tag ${node.status === 'honest' ? 'good' : 'warn'}`}>{node.status}</span></div>
            <h3>{node.id.replace('_', ' / ')}</h3><p className="muted">{node.validator ? 'Consensus validator' : 'Observer node'} · height {node.height}</p>
            <div className="trust"><span>Trust assessment</span><b>{fmt(node.trust_score)}<small>/100</small></b></div><progress max="100" value={node.trust_score} aria-label={`${node.id} trust score`} />
            <div className="node-meta"><span>{node.telemetry.votes} valid votes</span><span>{node.telemetry.timeouts} timeouts</span></div>
            <label className="scenario-label">Simulated behavior<select disabled={busy || !token} value={node.behavior} onChange={event => post('/simulation/scenarios', { node_id: node.id, behavior: event.target.value })}>{['honest', 'faulty', 'unavailable', 'malicious'].map(value => <option key={value}>{value}</option>)}</select></label>
          </article>)}</div></section>
          <section className="two-col"><div className="panel consensus"><p className="eyebrow">CONSENSUS STATUS</p><h2>{state.consensus.committed ? 'Quorum reached' : 'Awaiting quorum'}</h2><p className="muted">Signed prepare + commit votes · {metrics.quorum} required</p><div className="signal-bars" aria-hidden="true">{state.nodes.filter(n => n.validator).map(n => <span className={n.behavior === 'honest' && !n.quarantined ? 'on' : ''} key={n.id} />)}</div><div className="key-values"><span>Consensus stalls <b>{metrics.stalls}</b></span><span>Voting consistency <b>{fmt(metrics.voting_consistency * 100)}%</b></span><span>Transaction latency <b>{fmt(metrics.transaction_latency_ms)} ms</b></span><span>Block production delay <b>{fmt(metrics.block_delay_ms)} ms</b></span></div></div>
          <div className="panel"><p className="eyebrow">RECOVERY POLICY</p><h2>Safety before intervention</h2><p className="muted">Anomaly indicators carry evidence. A detector output alone cannot permanently ban a participant.</p><label className="policy-label">Operating mode<select value={state.mode} disabled={busy || !token} onChange={event => post('/healing/mode', { mode: event.target.value })}><option value="observe_only">Observe only</option><option value="approval_required">Human approval required</option><option value="autonomous_simulation">Autonomous local simulation</option></select></label><p className="policy-note">Reversible actions · quorum guard · cooldowns · rollback</p></div></section>
          <section id="alerts" className="panel"><div className="section-heading"><h2>Evidence & alerts</h2><span className="tag">{metrics.anomalies} recorded</span></div><p className="muted">An anomaly is an indicator, not proof of malicious intent.</p><div className="table-wrap"><table><thead><tr><th>Tick</th><th>Participant</th><th>Detection method</th><th>Confidence</th><th>Evidence</th></tr></thead><tbody>{state.alerts.slice(-8).reverse().map(a => <tr key={a.id}><td>{a.timestamp}</td><td>{a.node_id}</td><td>{a.method.replaceAll('_', ' ')}</td><td>{fmt(a.confidence * 100)}%</td><td><span className={`tag ${a.verified ? 'warn' : ''}`}>{a.verified ? 'Verified invalid vote' : 'Unverified indicator'}</span></td></tr>)}</tbody></table>{!state.alerts.length && <p className="empty">No alerts yet. Apply a fault scenario to explore the evidence pipeline.</p>}</div></section>
          <section id="recovery" className="panel"><div className="section-heading"><h2>Recovery journal</h2><span className="tag">{state.mode.replaceAll('_', ' ')}</span></div>{!state.recovery.length && <p className="empty">Recovery proposals will appear here with their reasons and outcomes.</p>}{state.recovery.slice(-6).reverse().map(r => <div className="journal" key={r.id}><span className="journal-icon">↻</span><div><b>{r.action} / {r.node_id}</b><p className="muted">{r.evidence.method} · trust {fmt(r.trust)} · tick {r.timestamp}</p>{r.reason && <small>{r.reason}</small>}</div><span className="tag">{r.status.replaceAll('_', ' ')}</span>{r.status === 'pending_approval' && <button disabled={busy || !token} onClick={() => post(`/healing/actions/${r.id}/approve`)}>Approve locally</button>}</div>)}</section>
        </>}
        <footer><span>LedgerShield / Research in network resilience</span><span>Simulator time · {metrics.simulated_seconds ?? 0}s</span></footer>
      </main>
    </div>
  )
}

function Metric({ label, value, suffix, detail }) {
  return <article className="panel metric"><p className="eyebrow">{label}</p><div className="metric-value">{value ?? 0}<small>{suffix}</small></div><p className="muted">{detail}</p></article>
}
