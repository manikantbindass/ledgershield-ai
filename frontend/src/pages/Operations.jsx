import { useState } from 'react'
import { useDashboard } from '../lib/context'
import { usePaged, useResource } from '../lib/hooks'
import { label, number, percent, short } from '../lib/utils'
import {
  Badge,
  Details,
  JSONDetails,
  KeyValues,
  LineChart,
  Pager,
  Panel,
  Resource,
  Search,
  Table,
} from '../components'

export function TrustManagement() {
  const { snapshot } = useDashboard()
  const [nodeId, setNodeId] = useState(snapshot.nodes[0]?.id || '')
  const node = snapshot.nodes.find((n) => n.id === nodeId) || snapshot.nodes[0]
  const history = useResource(`/trust/history?node_id=${encodeURIComponent(node.id)}&limit=100`)
  const settings = useResource('/settings', false)
  return (
    <>
      <Panel
        title="Explainable reputation"
        subtitle="Scores advise recovery; they never change consensus membership"
        action={
          <label>
            Participant
            <select value={node.id} onChange={(e) => setNodeId(e.target.value)}>
              {snapshot.nodes.map((n) => (
                <option key={n.id}>{n.id}</option>
              ))}
            </select>
          </label>
        }
      >
        <div className="trust-summary">
          <div>
            <strong>{number(node.trust_score)}</strong>
            <span>/ 100 trust score</span>
            <progress max="100" value={node.trust_score} aria-label={`${node.id} trust score`} />
          </div>
          <p>
            Every change references evidence, confidence and provenance. Transient latency or a
            single unverified detector signal cannot permanently ban a participant.
          </p>
        </div>
        <Resource resource={history}>
          {(data) => (
            <LineChart
              rows={[...data.items].reverse()}
              xKey="timestamp"
              yKey="after"
              title={`${node.id} trust score`}
              unit="points"
            />
          )}
        </Resource>
      </Panel>
      <div className="page-grid">
        <Panel
          title="Score components"
          subtitle="Contributions from the latest 100 records for this participant"
        >
          <Resource resource={history}>
            {(data) => {
              const components = {}
              data.items.forEach((row) => {
                components[row.kind] = (components[row.kind] || 0) + row.after - row.decayed
              })
              const decay = data.items.reduce((sum, row) => sum + row.decayed - row.before, 0)
              return (
                <>
                  <Table
                    rows={Object.entries(components).map(([kind, delta]) => ({ kind, delta }))}
                    rowKey="kind"
                    columns={[
                      { label: 'Evidence type', render: (r) => label(r.kind) },
                      {
                        label: 'Net contribution',
                        render: (r) => `${r.delta >= 0 ? '+' : ''}${number(r.delta, 3)}`,
                      },
                    ]}
                  />
                  <p className="chart-note">
                    Time-decay contribution: {number(decay, 3)} points. Saturation at score bounds
                    can limit applied changes.
                  </p>
                </>
              )
            }}
          </Resource>
        </Panel>
        <Panel title="Scoring policy" subtitle="Active bounded-score configuration">
          <Resource resource={settings}>
            {(data) => (
              <>
                <KeyValues
                  entries={[
                    ['Initial / neutral score', data.trust.initial],
                    ['Bounds', `${data.trust.minimum}–${data.trust.maximum}`],
                    ['Advisory threshold', data.trust.threshold],
                    ['Decay per simulator tick', data.trust.decay],
                    ['Verified violation weight', -data.trust.violation_weight],
                    ['Unverified indicator weight', -data.trust.detector_weight],
                  ]}
                />
                <code className="equation">
                  decayed = initial + (previous − initial) × (1 − decay)^elapsed
                  <br />
                  score = clamp(decayed + weight × confidence)
                </code>
              </>
            )}
          </Resource>
        </Panel>
      </div>
      <Panel title="Reputation history" subtitle="Newest first · latest 100 matching audit records">
        <Resource resource={history}>
          {(data) => (
            <>
              <Table
                rows={data.items}
                rowKey="evidence_id"
                columns={[
                  { label: 'Tick', key: 'timestamp' },
                  { label: 'Evidence', render: (r) => label(r.kind) },
                  { label: 'Before', render: (r) => number(r.before, 3) },
                  { label: 'After decay', render: (r) => number(r.decayed, 3) },
                  { label: 'After update', render: (r) => number(r.after, 3) },
                  { label: 'Confidence', render: (r) => percent(r.confidence) },
                  {
                    label: 'Provenance',
                    render: (r) => (
                      <details>
                        <summary>{r.provenance}</summary>
                        <code>{r.evidence_id}</code>
                        <p>{r.verified ? 'Verified evidence' : 'Unverified indicator'}</p>
                      </details>
                    ),
                  },
                ]}
              />
              <p className="chart-note">
                Showing {data.items.length} of {data.total} participant evidence records. This chart
                is a bounded recent window.
              </p>
            </>
          )}
        </Resource>
      </Panel>
    </>
  )
}

function HealingDetail({ id, onClose }) {
  const resource = useResource(`/healing/actions/${id}`)
  const { canAdmin, mutate } = useDashboard()
  return (
    <Details title={`Recovery audit / ${short(id)}`} onClose={onClose}>
      <Resource resource={resource}>
        {(record) => (
          <>
            <div className="detail-intro">
              <Badge tone={record.status === 'recovered' ? 'good' : 'warning'}>
                {label(record.status)}
              </Badge>
              <p>
                Fault evidence: {label(record.evidence.method)} · proposed action:{' '}
                <strong>{label(record.action)}</strong>
              </p>
            </div>
            <KeyValues
              entries={[
                ['Participant', record.node_id],
                ['Trust at proposal', number(record.trust)],
                ['Policy mode at proposal', label(record.proposed_mode)],
                ['Human approval required', record.approval_required ? 'Yes' : 'No'],
                ['Attempt', record.attempt ?? 'Not executed'],
                [
                  'Measured duration',
                  record.duration_ticks === null
                    ? 'Not available'
                    : `${record.duration_ticks} simulator ticks`,
                ],
                ['Collateral lagging nodes', record.collateral_nodes.join(', ') || 'None recorded'],
                ['Failure reason', record.reason || 'None recorded'],
              ]}
            />
            <h4>Recorded safety checks</h4>
            <JSONDetails value={record.safety_checks} title="Guard evaluation at execution" />
            <div className="outcome-grid">
              <div>
                <h4>Before intervention</h4>
                <KeyValues
                  entries={[
                    ['Blocks', record.before.blocks],
                    ['Stalls', record.before.stalls],
                    ['Availability', percent(record.before.availability)],
                  ]}
                />
              </div>
              <div>
                <h4>After intervention</h4>
                {record.after ? (
                  <KeyValues
                    entries={[
                      ['Blocks', record.after.blocks],
                      ['Stalls', record.after.stalls],
                      ['Availability', percent(record.after.availability)],
                    ]}
                  />
                ) : (
                  <p className="muted">
                    No measured execution outcome. Observe-only proposals do not execute.
                  </p>
                )}
              </div>
            </div>
            {record.status === 'pending_approval' && (
              <button
                className="primary"
                disabled={!canAdmin}
                onClick={() =>
                  mutate(
                    `/healing/actions/${id}/approve`,
                    {},
                    'Approval processed; inspect the recorded outcome',
                  )
                }
              >
                Approve local simulator action
              </button>
            )}
            <JSONDetails value={record} title="Complete immutable-context audit record" />
          </>
        )}
      </Resource>
    </Details>
  )
}

export function HealingCenter() {
  const { snapshot } = useDashboard()
  const resource = usePaged('/healing/actions')
  const [selected, setSelected] = useState(null)
  return (
    <>
      <div className="notice information">
        Operating mode: <strong>{label(snapshot.mode)}</strong>. Fixed quorum, evidence checks,
        cooldowns and retry limits protect simulator actions. No automatic validator deletion or
        consensus weakening.
      </div>
      <Panel
        title="Self-healing decisions"
        subtitle="A proposed action is distinct from execution and verified recovery"
      >
        <Search
          value={resource.q}
          onChange={resource.search}
          label="Filter recovery history"
          placeholder="Status, node, action or record ID"
        />
        <Resource resource={resource}>
          {(data) => (
            <>
              <Table
                rows={data.items}
                columns={[
                  { label: 'Tick', key: 'timestamp' },
                  {
                    label: 'Proposal',
                    render: (r) => (
                      <button className="link-button" onClick={() => setSelected(r.id)}>
                        {label(r.action)}
                      </button>
                    ),
                  },
                  { label: 'Participant', key: 'node_id' },
                  { label: 'Fault signal', render: (r) => label(r.evidence.method) },
                  {
                    label: 'Approval',
                    render: (r) => (r.approval_required ? 'Required' : 'Not required'),
                  },
                  {
                    label: 'Outcome',
                    render: (r) => (
                      <Badge
                        tone={
                          r.status === 'recovered'
                            ? 'good'
                            : r.status.includes('blocked') || r.status === 'rolled_back'
                              ? 'danger'
                              : ''
                        }
                      >
                        {label(r.status)}
                      </Badge>
                    ),
                  },
                ]}
              />
              <Pager resource={resource} />
            </>
          )}
        </Resource>
      </Panel>
      {selected && <HealingDetail id={selected} onClose={() => setSelected(null)} />}
    </>
  )
}

const scenarioInfo = {
  node_failure: ['Node failure', 'Temporarily make one participant unavailable.'],
  delay: ['Message delays', 'Raise simulated transport latency; configured timeouts still apply.'],
  partition: [
    'Network partition',
    'Split validators across deterministic groups and block cross-group delivery.',
  ],
  suspicious_voting: [
    'Suspicious voting',
    'A selected validator signs the wrong proposed block hash.',
  ],
  sybil_like: [
    'Sybil-like identities',
    'Introduce three correlated non-voting observer identities. Quorum membership stays fixed.',
  ],
  conflicting_transactions: [
    'Conflicting transfers',
    'Submit two validly signed transfers with the same nonce; observe the actual rejection.',
  ],
}

export function SimulationLab() {
  const { snapshot: s, canOperate, mutate, busy } = useDashboard()
  const [kind, setKind] = useState('node_failure'),
    [target, setTarget] = useState('node_1'),
    [duration, setDuration] = useState(5),
    [delay, setDelay] = useState(300)
  const runs = useResource('/simulation/runs?limit=100')
  const active = s.active_scenario
  const candidates = kind === 'suspicious_voting' ? s.nodes.filter((n) => n.validator) : s.nodes
  const node = candidates.some((n) => n.id === target) ? target : candidates[0].id
  async function submit(event) {
    event.preventDefault()
    await mutate(
      '/simulation/runs',
      { kind, node_id: node, duration_rounds: duration, latency_ms: delay },
      'Bounded scenario started in the local simulator',
    )
  }
  return (
    <>
      <div className="notice warning">
        Controlled simulation only. These scenarios demonstrate local behavior and do not prove
        resistance to real-world attacks. Demo keys and funds have no external value.
      </div>
      <div className="toolbar panel">
        <div>
          <strong>{s.running ? 'Simulation running' : 'Simulation paused'}</strong>
          <p>One background round every two wall-clock seconds while running.</p>
        </div>
        <div className="actions">
          <button
            disabled={!canOperate}
            onClick={() =>
              mutate(
                s.running ? '/simulation/stop' : '/simulation/start',
                {},
                s.running ? 'Simulation paused; state preserved' : 'Background simulation started',
              )
            }
          >
            {s.running ? 'Pause simulation' : 'Start simulation'}
          </button>
          <button
            disabled={!canOperate}
            onClick={() => mutate('/simulation/step', {}, 'One application round completed')}
          >
            Advance one round
          </button>
          <button
            disabled={!canOperate}
            onClick={() => mutate('/simulation/transaction', {}, 'Signed transfer staged')}
          >
            Signed demo transfer
          </button>
        </div>
      </div>
      <div className="page-grid wide-left">
        <Panel
          title="Scenario designer"
          subtitle="One active fault scenario at a time; maximum 20 simulator rounds"
        >
          <form onSubmit={submit} className="form-grid">
            <label className="span-two">
              Scenario
              <select
                value={kind}
                disabled={!!active || busy}
                onChange={(event) => setKind(event.target.value)}
              >
                {Object.entries(scenarioInfo).map(([key, [name]]) => (
                  <option key={key} value={key}>
                    {name}
                  </option>
                ))}
              </select>
            </label>
            <p className="form-help span-two">{scenarioInfo[kind][1]}</p>
            <label>
              Target participant
              <select
                value={node}
                disabled={!!active || busy}
                onChange={(e) => setTarget(e.target.value)}
              >
                {candidates.map((n) => (
                  <option key={n.id}>{n.id}</option>
                ))}
              </select>
            </label>
            <label>
              Duration in simulator rounds
              <input
                type="number"
                min="1"
                max="20"
                required
                value={duration}
                disabled={!!active || busy}
                onChange={(e) => setDuration(Number(e.target.value))}
              />
            </label>
            {kind === 'delay' && (
              <label>
                Simulated latency (ms)
                <input
                  type="number"
                  min="0"
                  max="5000"
                  value={delay}
                  required
                  onChange={(e) => setDelay(Number(e.target.value))}
                />
              </label>
            )}
            <div className="span-two">
              <button className="primary" disabled={!canOperate || !!active} type="submit">
                Start bounded scenario
              </button>
              <p className="form-help">
                Starts the background loop. At expiry, fault settings and the prior running state
                are restored. Recovery-driven quarantine, pending transfers, committed blocks and
                audit history are retained.
              </p>
            </div>
          </form>
        </Panel>
        <Panel title="Active scenario" subtitle="Expiry is checked after each application step">
          {active ? (
            <>
              <Badge tone="warning">{label(active.kind)}</Badge>
              <KeyValues
                entries={[
                  ['Run ID', <code>{active.id}</code>],
                  ['Target', active.node_id],
                  ['Started at', `tick ${active.started_at}`],
                  ['Expires at / after', `tick ${active.expires_at}`],
                  ['Current tick', s.metrics.simulated_seconds],
                ]}
              />
              <button
                className="danger-button"
                disabled={!canOperate}
                onClick={() =>
                  mutate(
                    `/simulation/runs/${active.id}/stop`,
                    {},
                    'Scenario stopped; fault settings restored',
                  )
                }
              >
                Stop scenario and restore settings
              </button>
              <JSONDetails value={active.details} title="Scenario parameters and observed result" />
            </>
          ) : (
            <div className="scenario-idle">
              <IconPlaceholder />
              <h3>No active scenario</h3>
              <p>Choose a fault and a bounded duration to begin a repeatable local experiment.</p>
            </div>
          )}
        </Panel>
      </div>
      <Panel
        title="Scenario run history"
        subtitle="Actual runs from this in-memory service instance"
      >
        <Resource resource={runs}>
          {(data) => (
            <Table
              rows={data.items}
              columns={[
                {
                  label: 'Run',
                  render: (r) => (
                    <details>
                      <summary>
                        <code>{short(r.id)}</code>
                      </summary>
                      <JSONDetails value={r.details} title="Parameters / results" />
                    </details>
                  ),
                },
                { label: 'Scenario', render: (r) => label(r.kind) },
                { label: 'Target', key: 'node_id' },
                { label: 'Started', render: (r) => `tick ${r.started_at}` },
                {
                  label: 'Ended',
                  render: (r) => (r.ended_at === null ? 'Active' : `tick ${r.ended_at}`),
                },
                {
                  label: 'Status',
                  render: (r) => (
                    <Badge tone={r.status === 'running' ? 'warning' : 'good'}>{r.status}</Badge>
                  ),
                },
              ]}
            />
          )}
        </Resource>
      </Panel>
    </>
  )
}
function IconPlaceholder() {
  return (
    <span className="scenario-glyph" aria-hidden="true">
      ▷
    </span>
  )
}

export function SettingsAudit() {
  const { snapshot, role, login, logout, canAdmin, mutate, diagnostics, connection } =
    useDashboard()
  const settings = useResource('/settings'),
    health = useResource('/health')
  const events = usePaged('/audit/events')
  const [draft, setDraft] = useState(''),
    [authBusy, setAuthBusy] = useState(false),
    [mode, setMode] = useState(snapshot.mode)
  const [config, setConfig] = useState({
    seed: snapshot.config.seed,
    node_count: snapshot.config.node_count,
    validator_count: snapshot.config.validator_count,
  })
  const [acknowledged, setAcknowledged] = useState(false)
  async function authenticate(e) {
    e.preventDefault()
    setAuthBusy(true)
    if (await login(draft.trim())) setDraft('')
    setAuthBusy(false)
  }
  async function reset(e) {
    e.preventDefault()
    const result = await mutate(
      '/simulation/reset',
      config,
      'Local simulation reset to paused observe-only mode',
    )
    if (result) setAcknowledged(false)
  }
  return (
    <>
      <div className="page-grid">
        <Panel
          title="Local access"
          subtitle="Bearer credentials stay only in this tab's memory"
          action={<Badge tone={role === 'admin' ? 'good' : ''}>{role}</Badge>}
        >
          <form onSubmit={authenticate} className="stack">
            <label>
              Operator or admin token
              <input
                type="password"
                autoComplete="off"
                required
                minLength="32"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder="Read your local .env file"
              />
            </label>
            <div className="actions">
              <button className="primary" disabled={authBusy || connection !== 'live'}>
                Verify token
              </button>
              <button type="button" disabled={role === 'viewer'} onClick={logout}>
                Clear access
              </button>
            </div>
          </form>
          <p className="form-help">
            Operators: scenarios, signed transactions, evaluations. Admins: also mode changes,
            approvals and reset. No token is written to browser storage.
          </p>
        </Panel>
        <Panel
          title="Service diagnostics"
          subtitle="Explicitly in-memory, single-process local research service"
        >
          <Resource resource={health}>
            {(data) => (
              <KeyValues
                entries={[
                  ['API status', data.status],
                  ['Chain state replay', data.integrity ? 'Verified' : 'Failed'],
                  ['Background loop', data.running ? 'Running' : 'Paused'],
                  ['Storage', label(data.storage)],
                  ['Live policy', 'Rule-based'],
                  ['Service instance', <code>{snapshot.instance_id}</code>],
                ]}
              />
            )}
          </Resource>
          <a
            className="text-link"
            href="http://127.0.0.1:8000/docs"
            target="_blank"
            rel="noreferrer"
          >
            Open versioned API documentation ↗
          </a>
        </Panel>
      </div>
      <div className="page-grid">
        <Panel title="Recovery operating mode" subtitle={`Currently ${label(snapshot.mode)}`}>
          <form
            onSubmit={(e) => {
              e.preventDefault()
              mutate('/healing/mode', { mode }, 'Recovery operating mode updated')
            }}
            className="stack"
          >
            <label>
              Proposed mode
              <select value={mode} onChange={(e) => setMode(e.target.value)} disabled={!canAdmin}>
                <option value="observe_only">Observe only</option>
                <option value="approval_required">Human approval required</option>
                <option value="autonomous_simulation">Autonomous local simulation</option>
              </select>
            </label>
            <button disabled={!canAdmin || mode === snapshot.mode}>Apply recovery mode</button>
            <p className="form-help">
              This never enables external disruptive actions or weakens quorum.
            </p>
          </form>
        </Panel>
        <Panel
          title="Reset simulator configuration"
          subtitle="Admin only · clears the local ledger and simulator history"
        >
          <form onSubmit={reset} className="form-grid">
            {Object.entries(config).map(([key, value]) => (
              <label key={key}>
                {label(key)}
                <input
                  type="number"
                  required
                  min={key === 'seed' ? 0 : 4}
                  max={
                    key === 'seed' ? 2 ** 30 : key === 'validator_count' ? config.node_count : 100
                  }
                  disabled={!canAdmin}
                  value={value}
                  onChange={(e) => setConfig({ ...config, [key]: Number(e.target.value) })}
                />
              </label>
            ))}
            <label className="checkbox span-two">
              <input
                type="checkbox"
                checked={acknowledged}
                required
                disabled={!canAdmin}
                onChange={(e) => setAcknowledged(e.target.checked)}
              />
              I understand that simulator state will be cleared.
            </label>
            <button className="danger-button span-two" disabled={!canAdmin || !acknowledged}>
              Reset local simulation
            </button>
          </form>
        </Panel>
      </div>
      <Panel
        title="Safe configuration"
        subtitle="No credentials, private keys or server paths are returned"
      >
        <Resource resource={settings}>
          {(data) => (
            <JSONDetails value={data} title="Inspect active settings, weights and limits" />
          )}
        </Resource>
      </Panel>
      <Panel
        title="Server event history"
        subtitle="Latest 500 server-recorded events; newest first"
      >
        <Search
          value={events.q}
          onChange={events.search}
          label="Filter audit events"
          placeholder="Event type, description or event ID"
        />
        <Resource resource={events}>
          {(data) => (
            <>
              <Table
                rows={data.items}
                columns={[
                  { label: 'Tick', key: 'timestamp' },
                  { label: 'Type', render: (r) => <Badge>{label(r.kind)}</Badge> },
                  { label: 'Description', key: 'summary' },
                  {
                    label: 'Context',
                    render: (r) => (
                      <details>
                        <summary>Inspect event</summary>
                        <pre>{JSON.stringify(r.details, null, 2)}</pre>
                      </details>
                    ),
                  },
                ]}
              />
              <Pager resource={events} />
            </>
          )}
        </Resource>
      </Panel>
      <Panel title="Client error diagnostics" subtitle="Latest 20 errors observed in this tab">
        <Table
          rows={diagnostics}
          rowKey="at"
          columns={[
            { label: 'Observed at', key: 'at' },
            { label: 'Code', key: 'code' },
            { label: 'Message', key: 'message' },
            { label: 'Request ID', render: (r) => <code>{r.request_id || 'Not supplied'}</code> },
          ]}
          empty="No client request errors have been recorded in this tab."
        />
      </Panel>
    </>
  )
}
