import { useState } from 'react'
import { useDashboard } from '../lib/context'
import { usePaged, useResource } from '../lib/hooks'
import { label, number, percent, short } from '../lib/utils'
import {
  Badge,
  Details,
  Empty,
  Icon,
  JSONDetails,
  KeyValues,
  LineChart,
  Metric,
  Pager,
  Panel,
  Resource,
  Search,
  Table,
} from '../components'

export function Overview() {
  const { snapshot: s, canOperate, mutate } = useDashboard()
  const [metric, setMetric] = useState('throughput')
  const [window, setWindow] = useState(30)
  const m = s.metrics
  return (
    <>
      <section className="status-hero">
        <div>
          <span className="eyebrow">CANONICAL NETWORK / LOCAL SIMULATION</span>
          <h2>
            {s.consensus.committed
              ? 'Consensus is progressing.'
              : s.consensus.reason === 'not_started'
                ? 'Ready for the first round.'
                : 'Consensus needs attention.'}
          </h2>
          <p>
            {s.nodes.filter((n) => n.status === 'honest').length} honest participants ·{' '}
            {s.config.validator_count} fixed validators · quorum {m.quorum}
          </p>
        </div>
        <div className="hero-symbol">
          <Icon name="security" size={65} />
          <span className={s.consensus.committed ? 'pulse-dot' : 'pulse-dot paused'} />
        </div>
      </section>
      <div className="metric-grid">
        <Metric
          title="Block height"
          value={number(m.height, 0)}
          detail={`View ${m.view} · ${m.stalls} recorded stalls`}
          icon="blockchain"
        />
        <Metric
          title="Transaction throughput"
          value={number(m.throughput, 3)}
          suffix="tx / sim s"
          detail={`${m.committed_transactions} committed · ${m.rejected} rejected`}
          icon="reports"
        />
        <Metric
          title="Mean message latency"
          value={number(m.message_latency_ms)}
          suffix="ms"
          detail={`${m.timeouts} delivery timeouts`}
          icon="network"
        />
        <Metric
          title="Validator participation"
          value={percent(m.participation)}
          detail={`${percent(m.voting_consistency)} valid-vote consistency`}
          icon="trust"
        />
      </div>
      <div className="page-grid wide-left">
        <Panel
          title="Network activity"
          subtitle="Measured simulator samples; no generated chart values"
          action={
            <div className="inline-fields">
              <label>
                Metric
                <select value={metric} onChange={(e) => setMetric(e.target.value)}>
                  <option value="throughput">Throughput</option>
                  <option value="message_latency_ms">Message latency</option>
                  <option value="availability">Availability</option>
                  <option value="height">Block height</option>
                  <option value="stalls">Stalls</option>
                </select>
              </label>
              <label>
                Samples
                <select value={window} onChange={(e) => setWindow(Number(e.target.value))}>
                  <option value={30}>Last 30</option>
                  <option value={120}>Last 120</option>
                  <option value={240}>Last 240</option>
                </select>
              </label>
            </div>
          }
        >
          <LineChart rows={s.history.slice(-window)} yKey={metric} title={label(metric)} />
        </Panel>
        <Panel title="Network pulse" subtitle="Current configured state">
          <div className="ring-stat">
            <svg
              viewBox="0 0 120 120"
              aria-label={`${percent(m.availability)} node availability`}
              role="img"
            >
              <circle cx="60" cy="60" r="48" className="ring-base" />
              <circle
                cx="60"
                cy="60"
                r="48"
                className="ring-value"
                strokeDasharray={`${m.availability * 302} 302`}
              />
            </svg>
            <div>
              <strong>{percent(m.availability)}</strong>
              <span>node availability</span>
            </div>
          </div>
          <KeyValues
            entries={[
              ['Participants', s.nodes.length],
              ['Alerts', m.anomalies],
              ['Verified recoveries', m.recovery_successes],
              ['Recovery rollbacks', m.recovery_failures],
            ]}
          />
        </Panel>
      </div>
      <div className="toolbar panel">
        <div>
          <strong>Observe a signed transfer</strong>
          <p>Stage a transfer from the public simulator wallet, then advance consensus.</p>
        </div>
        <div className="actions">
          <button
            className="primary"
            disabled={!canOperate}
            onClick={() =>
              mutate('/simulation/transaction', {}, 'Signed transfer staged in the mempool')
            }
          >
            + Signed transfer
          </button>
          <button
            disabled={!canOperate}
            onClick={() => mutate('/simulation/step', {}, 'Consensus round completed')}
          >
            Advance round <Icon name="arrow" size={15} />
          </button>
        </div>
      </div>
      <div className="page-grid">
        <Panel
          title="Security signals"
          subtitle="Indicators are not proof of malicious intent"
          action={
            <a className="text-link" href="#/security">
              Open security →
            </a>
          }
        >
          {s.alerts.length ? (
            s.alerts
              .slice(-4)
              .reverse()
              .map((a) => (
                <div className="feed-row" key={a.id}>
                  <span className="signal-marker warning" />
                  <div>
                    <strong>{label(a.method)}</strong>
                    <p>
                      {a.node_id} · tick {a.timestamp}
                    </p>
                  </div>
                  <Badge tone={a.verified ? 'warning' : ''}>{a.severity}</Badge>
                </div>
              ))
          ) : (
            <Empty title="No security alerts">
              Introduce a controlled fault in Simulation Lab to observe its evidence.
            </Empty>
          )}
        </Panel>
        <Panel
          title="Recent recovery decisions"
          subtitle={`${label(s.mode)} mode`}
          action={
            <a className="text-link" href="#/healing">
              Open healing →
            </a>
          }
        >
          {s.recovery.length ? (
            s.recovery
              .slice(-4)
              .reverse()
              .map((r) => (
                <div className="feed-row" key={r.id}>
                  <Icon name="healing" />
                  <div>
                    <strong>
                      {label(r.action)} · {r.node_id}
                    </strong>
                    <p>{label(r.evidence.method)}</p>
                  </div>
                  <Badge tone={r.status === 'recovered' ? 'good' : ''}>{label(r.status)}</Badge>
                </div>
              ))
          ) : (
            <Empty title="No recovery proposals">
              Proposals and outcomes appear after the evidence pipeline runs.
            </Empty>
          )}
        </Panel>
      </div>
      <Panel title="Recent network events" subtitle="Server-recorded activity, newest first">
        <Table
          rows={s.recent_events.slice(-5).reverse()}
          columns={[
            { label: 'Tick', key: 'timestamp' },
            { label: 'Event', render: (r) => <Badge>{label(r.kind)}</Badge> },
            { label: 'Description', key: 'summary' },
          ]}
        />
      </Panel>
    </>
  )
}

function Topology({ nodes, partitions, selected, onSelect }) {
  const visible = nodes.slice(0, 24)
  const point = (i) => {
    const angle = (2 * Math.PI * i) / visible.length - Math.PI / 2
    return [360 + Math.cos(angle) * 220, 190 + Math.sin(angle) * 145]
  }
  const blocked = new Set(partitions.map((p) => [...p].sort().join(':')))
  return (
    <>
      <svg
        className="topology"
        viewBox="0 0 720 390"
        role="group"
        aria-label="Simulated node topology. Select a participant to inspect it."
      >
        {visible.flatMap((node, i) =>
          visible.slice(i + 1).map((other, j) => {
            const available =
              !blocked.has([node.id, other.id].sort().join(':')) &&
              !node.quarantined &&
              !other.quarantined &&
              node.behavior !== 'unavailable' &&
              other.behavior !== 'unavailable'
            return (
              <line
                key={`${node.id}:${other.id}`}
                x1={point(i)[0]}
                y1={point(i)[1]}
                x2={point(i + 1 + j)[0]}
                y2={point(i + 1 + j)[1]}
                className={available ? 'edge' : 'edge blocked'}
              />
            )
          }),
        )}
        {visible.map((node, i) => {
          const [x, y] = point(i)
          return (
            <g
              key={node.id}
              className={`graph-node ${selected === node.id ? 'chosen' : ''} ${node.quarantined || node.behavior !== 'honest' ? 'fault' : ''}`}
              role="button"
              tabIndex="0"
              aria-label={`Inspect ${node.id}, ${node.validator ? 'validator' : 'observer'}, ${node.status}`}
              aria-pressed={selected === node.id}
              onClick={() => onSelect(node.id)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault()
                  onSelect(node.id)
                }
              }}
            >
              <circle cx={x} cy={y} r={node.validator ? 23 : 16} />
              <text x={x} y={y + 4} textAnchor="middle">
                {node.validator ? 'V' : 'O'}
              </text>
              <text x={x} y={y + 43} textAnchor="middle" className="graph-label">
                {node.id}
              </text>
            </g>
          )
        })}
      </svg>
      <p className="chart-note">
        {visible.length} of {nodes.length} matching participants shown. V = fixed validator · O =
        observer. Dashed links are unreachable by configuration; delivery also depends on latency
        and loss.
      </p>
    </>
  )
}

export function NetworkExplorer() {
  const { snapshot: s } = useDashboard()
  const [query, setQuery] = useState(''),
    [role, setRole] = useState('all'),
    [selected, setSelected] = useState(null)
  const nodes = s.nodes.filter(
    (n) =>
      `${n.id} ${n.status}`.toLowerCase().includes(query.toLowerCase()) &&
      (role === 'all' || n.validator === (role === 'validators')),
  )
  const node = s.nodes.find((n) => n.id === selected)
  return (
    <>
      <Panel
        title="Participant topology"
        subtitle="Logical all-to-all simulator links; not a physical peer-to-peer map"
        action={<Badge>{s.partitioned_links.length} partitioned links</Badge>}
      >
        <div className="filter-row">
          <Search
            value={query}
            onChange={setQuery}
            label="Search participants"
            placeholder="Node ID or status"
          />
          <label>
            Role
            <select value={role} onChange={(e) => setRole(e.target.value)}>
              <option value="all">All roles</option>
              <option value="validators">Validators</option>
              <option value="observers">Observers</option>
            </select>
          </label>
        </div>
        {nodes.length ? (
          <Topology
            nodes={nodes}
            partitions={s.partitioned_links}
            selected={selected}
            onSelect={setSelected}
          />
        ) : (
          <Empty title="No matching participants" />
        )}
      </Panel>
      {node && (
        <Details title={`Participant / ${node.id}`} onClose={() => setSelected(null)}>
          <KeyValues
            entries={[
              ['Public identity', <code>{node.identity}</code>],
              ['Membership', node.validator ? 'Fixed validator' : 'Non-voting observer'],
              ['Behavior', label(node.behavior)],
              ['Quarantine', node.quarantined ? 'Active' : 'Not quarantined'],
              ['Trust', `${number(node.trust_score)} / 100`],
              ['Replica height', node.height],
              ['Monitoring', node.monitoring ? 'Increased' : 'Standard'],
            ]}
          />
          <JSONDetails value={node.telemetry} title="Measured node telemetry" />
        </Details>
      )}
      <Panel
        title="Node directory"
        subtitle="Click a participant for its public identity and observed state"
      >
        <Table
          rows={nodes}
          columns={[
            {
              label: 'Participant',
              render: (n) => (
                <button className="link-button" onClick={() => setSelected(n.id)}>
                  {n.id}
                </button>
              ),
            },
            { label: 'Role', render: (n) => (n.validator ? 'Validator' : 'Observer') },
            {
              label: 'Status',
              render: (n) => (
                <Badge tone={n.status === 'honest' ? 'good' : 'warning'}>{label(n.status)}</Badge>
              ),
            },
            { label: 'Trust', render: (n) => `${number(n.trust_score)} / 100` },
            { label: 'Height', key: 'height' },
            { label: 'Valid votes', render: (n) => n.telemetry.votes },
            { label: 'Timeouts', render: (n) => n.telemetry.timeouts },
          ]}
        />
      </Panel>
    </>
  )
}

function BlockDetails({ height, onClose }) {
  const resource = useResource(`/blocks/${height}`, false)
  return (
    <Details title={`Block / ${height}`} onClose={onClose}>
      <Resource resource={resource}>
        {(data) => (
          <>
            <div className="actions">
              <Badge tone={data.hash_valid && data.parent_valid ? 'good' : 'danger'}>
                {data.hash_valid && data.parent_valid
                  ? 'Hash & linkage verified'
                  : 'Integrity failure'}
              </Badge>
              <Badge>{label(data.consensus)} consensus</Badge>
              <Badge tone={data.state_integrity ? 'good' : 'danger'}>
                State replay {data.state_integrity ? 'verified' : 'failed'}
              </Badge>
            </div>
            <KeyValues
              entries={[
                ['Block hash', <code>{data.block.hash}</code>],
                ['Parent hash', <code>{data.block.previous_hash}</code>],
                ['Merkle root', <code>{data.block.merkle_root}</code>],
                ['Simulated timestamp', `tick ${data.block.timestamp}`],
                ['Proposer', data.block.validator],
                ['Transaction count', data.block.transactions.length],
              ]}
            />
            <JSONDetails value={data.block} title="Canonical block and transactions" />
          </>
        )}
      </Resource>
    </Details>
  )
}

export function BlockchainExplorer() {
  const blocks = usePaged('/blocks'),
    transactions = usePaged('/transactions')
  const [tab, setTab] = useState('blocks'),
    [height, setHeight] = useState(null),
    [tx, setTx] = useState(null)
  const resource = tab === 'blocks' ? blocks : transactions
  return (
    <>
      <div className="tabs" role="group" aria-label="Ledger collection">
        <button aria-pressed={tab === 'blocks'} onClick={() => setTab('blocks')}>
          Blocks
        </button>
        <button aria-pressed={tab === 'transactions'} onClick={() => setTab('transactions')}>
          Transactions
        </button>
      </div>
      <Panel
        title={tab === 'blocks' ? 'Canonical blocks' : 'Signed transaction history'}
        subtitle="Timestamps are simulated ticks. Mempool acceptance is separate from consensus finality."
      >
        <Search
          label={`Search ${tab}`}
          value={resource.q}
          onChange={resource.search}
          placeholder={
            tab === 'blocks'
              ? 'Height, hash or proposer'
              : 'Transaction ID, status or rejection code'
          }
        />
        <Resource resource={resource}>
          {(data) => (
            <>
              <Table
                rows={data.items}
                rowKey={tab === 'blocks' ? 'hash' : 'tx_hash'}
                columns={
                  tab === 'blocks'
                    ? [
                        {
                          label: 'Height',
                          render: (b) => (
                            <button className="link-button" onClick={() => setHeight(b.index)}>
                              #{b.index}
                            </button>
                          ),
                        },
                        {
                          label: 'Hash',
                          render: (b) => <code title={b.hash}>{short(b.hash, 18)}</code>,
                        },
                        {
                          label: 'Previous hash',
                          render: (b) => (
                            <code title={b.previous_hash}>{short(b.previous_hash, 14)}</code>
                          ),
                        },
                        { label: 'Timestamp', render: (b) => `tick ${b.timestamp}` },
                        { label: 'Transactions', render: (b) => b.transactions.length },
                        { label: 'Proposer', key: 'validator' },
                      ]
                    : [
                        {
                          label: 'Transaction',
                          render: (t) => (
                            <button className="link-button mono" onClick={() => setTx(t)}>
                              {short(t.tx_hash, 18)}
                            </button>
                          ),
                        },
                        {
                          label: 'Status',
                          render: (t) => (
                            <Badge
                              tone={
                                t.status === 'committed'
                                  ? 'good'
                                  : t.status === 'rejected'
                                    ? 'danger'
                                    : ''
                              }
                            >
                              {t.status}
                            </Badge>
                          ),
                        },
                        { label: 'Amount', render: (t) => `${t.transaction.amount} units` },
                        { label: 'Nonce', render: (t) => t.transaction.nonce },
                        { label: 'Submitted', render: (t) => `tick ${t.submitted_at}` },
                        {
                          label: 'Outcome',
                          render: (t) =>
                            t.rejection_code ||
                            (t.committed_at !== null
                              ? `Committed at ${t.committed_at}`
                              : 'Awaiting consensus'),
                        },
                      ]
                }
              />
              <Pager resource={resource} />
            </>
          )}
        </Resource>
      </Panel>
      {height !== null && <BlockDetails height={height} onClose={() => setHeight(null)} />}
      {tx && (
        <Details title={`Transaction / ${short(tx.tx_hash)}`} onClose={() => setTx(null)}>
          <KeyValues
            entries={[
              ['Transaction hash', <code>{tx.tx_hash}</code>],
              ['Sender public key', <code>{tx.transaction.sender}</code>],
              ['Receiver public key', <code>{tx.transaction.receiver}</code>],
              ['Amount', `${tx.transaction.amount} integer units`],
              ['Nonce', tx.transaction.nonce],
              ['Outcome', tx.rejection_code || tx.status],
            ]}
          />
          <JSONDetails value={tx} title="Signed transaction record" />
        </Details>
      )}
    </>
  )
}

const classifications = {
  invalid_signed_vote: 'Protocol vote violation',
  repeated_timeout: 'Availability signal',
  isolation_forest: 'Statistical anomaly indicator',
}
export function SecurityCenter() {
  const resource = usePaged('/alerts')
  const [selected, setSelected] = useState(null)
  return (
    <>
      <div className="notice information">
        Anomaly scores and confidence values are indicators, not calibrated probabilities or proof
        of malicious intent. All traffic is simulated.
      </div>
      <Panel title="Security evidence" subtitle="Search the complete in-memory alert history">
        <Search
          value={resource.q}
          onChange={resource.search}
          label="Filter security alerts"
          placeholder="Severity, detection method or node ID"
        />
        <Resource resource={resource}>
          {(data) => (
            <>
              <Table
                rows={data.items}
                columns={[
                  { label: 'Tick', key: 'timestamp' },
                  {
                    label: 'Classification',
                    render: (a) => (
                      <button className="link-button" onClick={() => setSelected(a)}>
                        {classifications[a.method] || label(a.method)}
                      </button>
                    ),
                  },
                  {
                    label: 'Severity',
                    render: (a) => (
                      <Badge tone={a.severity === 'high' ? 'danger' : 'warning'}>
                        {a.severity}
                      </Badge>
                    ),
                  },
                  { label: 'Participant', key: 'node_id' },
                  { label: 'Confidence', render: (a) => percent(a.confidence) },
                  {
                    label: 'Provenance',
                    render: (a) =>
                      a.verified ? 'Verified signed violation' : 'Unverified indicator',
                  },
                ]}
              />
              <Pager resource={resource} />
            </>
          )}
        </Resource>
      </Panel>
      {selected && (
        <Details
          title={classifications[selected.method] || label(selected.method)}
          onClose={() => setSelected(null)}
        >
          <p>{selected.explanation}</p>
          <KeyValues
            entries={[
              ['Alert ID', <code>{selected.id}</code>],
              ['Node', selected.node_id],
              ['Method', label(selected.method)],
              ['Severity', selected.severity],
              ['Confidence (heuristic)', percent(selected.confidence)],
              ['Anomaly score', number(selected.anomaly_score, 5)],
              ['Recorded at', `tick ${selected.timestamp}`],
            ]}
          />
          <JSONDetails
            value={{
              features: selected.features,
              evidence: selected.evidence,
              verified: selected.verified,
            }}
            title="Raw features and supporting evidence"
          />
        </Details>
      )}
    </>
  )
}
