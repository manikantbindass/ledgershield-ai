import { useState } from 'react'
import { useDashboard } from '../lib/context'
import { usePaged, useResource } from '../lib/hooks'
import { download, label, matchedExperiments, number, short } from '../lib/utils'
import {
  Badge,
  BarChart,
  Details,
  Empty,
  JSONDetails,
  KeyValues,
  LineChart,
  Pager,
  Panel,
  Resource,
  Search,
  Table,
} from '../components'

export function RLLab() {
  const resource = useResource('/learning/runs', false)
  const { refresh } = useDashboard()
  const [metric, setMetric] = useState('reward')
  return (
    <>
      <div className="notice information">
        The live recovery service uses a rule policy. Training is an explicit offline workflow; this
        page does not train, replace or deploy policies.
      </div>
      <Resource resource={resource}>
        {(data) => (
          <>
            <div className="page-grid">
              <Panel
                title="Recorded training run"
                subtitle={data.source}
                action={
                  <Badge>{data.run_id ? 'Recorded offline training' : 'No training record'}</Badge>
                }
              >
                <KeyValues
                  entries={[
                    ['Run identifier', data.run_id || 'Not available'],
                    ['Recorded episodes', data.training.length],
                    ['Parameter updates', data.updates],
                    ['Learning implementation', 'NumPy DQN · replay + target network'],
                  ]}
                />
                <p className="form-help">
                  Training execution is evidence that updates ran, not that resilience improved.
                </p>
                <div className="actions">
                  <button onClick={refresh}>Refresh recorded runs</button>
                  <button
                    disabled={!data.run_id}
                    onClick={() => download(`${data.run_id}.json`, data)}
                  >
                    Export run JSON
                  </button>
                </div>
              </Panel>
              <Panel
                title="Current checkpoint metadata"
                subtitle="Availability is independent of deployment status"
              >
                <Badge tone={data.model.status === 'trained' ? 'good' : 'warning'}>
                  {label(data.model.status)}
                </Badge>
                <KeyValues
                  entries={[
                    ['Parameter updates', data.model.updates],
                    ['Network dimensions', data.model.architecture.join(' → ')],
                    ['Live policy', 'Rule-based'],
                    ['Automatic deployment', 'Disabled'],
                  ]}
                />
                <p className="form-help">
                  A historical training record can exist while the local checkpoint is missing.
                  Missing or invalid checkpoints use the rule fallback during evaluation.
                </p>
              </Panel>
            </div>
            <Panel
              title="Learning curves"
              subtitle="Values come from the recorded experiment manifest"
              action={
                <label>
                  Series
                  <select value={metric} onChange={(e) => setMetric(e.target.value)}>
                    <option value="reward">Episode reward</option>
                    <option value="loss" disabled={!data.training.some((r) => r.loss !== null)}>
                      Mean TD loss{' '}
                      {data.training.some((r) => r.loss !== null) ? '' : '(not recorded)'}
                    </option>
                  </select>
                </label>
              }
            >
              <LineChart
                rows={data.training.filter((row) => row[metric] !== null)}
                xKey="episode"
                yKey={metric}
                title={metric === 'reward' ? 'Episode reward' : 'Mean TD loss'}
              />
            </Panel>
            <Panel
              title="Historical held-out evaluation"
              subtitle="Published measurements; separate seeds from training"
            >
              <BarChart rows={data.evaluation} title="Historical mean episode reward by policy" />
              <Table
                rows={data.evaluation}
                rowKey="policy"
                columns={[
                  { label: 'Policy', render: (r) => label(r.policy) },
                  { label: 'Episodes', key: 'episodes' },
                  { label: 'Mean reward', render: (r) => number(r.mean_reward, 3) },
                  { label: 'Committed transfers', key: 'committed_transactions' },
                  { label: 'Verified recoveries', key: 'recoveries' },
                ]}
              />
              <p className="chart-note">
                {data.claim} The recorded DQN did not outperform the no-healing baseline.{' '}
                <a className="text-link" href="#/reports">
                  Run a matched comparison →
                </a>
              </p>
            </Panel>
          </>
        )}
      </Resource>
    </>
  )
}

function standardDeviation(rows) {
  if (rows.length < 2) return null
  const mean = rows.reduce((sum, row) => sum + row.reward, 0) / rows.length
  return Math.sqrt(rows.reduce((sum, row) => sum + (row.reward - mean) ** 2, 0) / (rows.length - 1))
}

export function ExperimentReports() {
  const resource = usePaged('/experiments')
  const { canOperate, mutate } = useDashboard()
  const [form, setForm] = useState({ episodes: 4, horizon: 10, seed: 20000 })
  const [selected, setSelected] = useState({})
  const [detail, setDetail] = useState(null)
  const records = Object.values(selected)
  const matched = matchedExperiments(records)
  async function compare(event) {
    event.preventDefault()
    const result = await mutate(
      '/policies/compare',
      form,
      'Matched policy evaluation completed; results recorded',
    )
    if (result) setSelected(Object.fromEntries(result.experiments.map((r) => [r.id, r])))
  }
  function toggle(record) {
    setSelected((previous) => {
      const next = { ...previous }
      if (next[record.id]) delete next[record.id]
      else next[record.id] = record
      return next
    })
  }
  const rows = records.flatMap((record) =>
    record.results.map((row) => ({
      experiment_id: record.id,
      policy: record.actual_policy,
      seed: row.seed,
      scenario: row.scenario,
      reward: row.reward,
      recoveries: row.recoveries,
      throughput: row.metrics.throughput,
      committed_transactions: row.metrics.committed_transactions,
      stalls: row.metrics.stalls,
      latency_ms: row.metrics.message_latency_ms,
    })),
  )
  return (
    <>
      <Panel
        title="Matched baseline comparison"
        subtitle="Evaluates no-healing, rule and requested DQN policies in isolated simulators"
      >
        <form onSubmit={compare} className="comparison-form">
          {Object.entries(form).map(([key, value]) => (
            <label key={key}>
              {key === 'horizon' ? 'Episode horizon' : label(key)}
              <input
                type="number"
                required
                min={key === 'seed' ? 10000 : 1}
                max={key === 'seed' ? 2 ** 30 : key === 'episodes' ? 4 : 20}
                value={value}
                onChange={(e) => setForm({ ...form, [key]: Number(e.target.value) })}
              />
            </label>
          ))}
          <button className="primary" disabled={!canOperate}>
            Run matched comparison
          </button>
        </form>
        <p className="form-help">
          Same seeds, scenarios, horizon and reward configuration. At most 240 total environment
          steps; three evaluation requests per role per minute. A missing checkpoint is explicitly
          labeled as a rule fallback. The live ledger is not changed.
        </p>
      </Panel>
      <Panel
        title="Experiment registry"
        subtitle="API-created in-memory records; offline results are shown separately in RL Lab"
      >
        <Search
          value={resource.q}
          onChange={resource.search}
          label="Search experiment registry"
          placeholder="Run ID, policy or comparison group"
        />
        <Resource resource={resource}>
          {(data) => (
            <>
              <Table
                rows={data.items}
                columns={[
                  {
                    label: 'Compare',
                    render: (r) => (
                      <input
                        type="checkbox"
                        aria-label={`Compare experiment ${r.id}`}
                        checked={!!selected[r.id]}
                        onChange={() => toggle(r)}
                      />
                    ),
                  },
                  {
                    label: 'Run identifier',
                    render: (r) => (
                      <button className="link-button mono" onClick={() => setDetail(r)}>
                        {short(r.id)}
                      </button>
                    ),
                  },
                  {
                    label: 'Actual policy',
                    render: (r) => (
                      <Badge tone={r.actual_policy === 'rule_fallback' ? 'warning' : ''}>
                        {label(r.actual_policy)}
                      </Badge>
                    ),
                  },
                  { label: 'Episodes', key: 'episodes' },
                  { label: 'Mean reward', render: (r) => number(r.mean_reward, 3) },
                  { label: 'Evaluation seed', key: 'seed' },
                  {
                    label: 'Created (UTC)',
                    render: (r) => r.created_at.replace('T', ' ').slice(0, 19),
                  },
                ]}
              />
              <Pager resource={resource} />
            </>
          )}
        </Resource>
      </Panel>
      <Panel
        title="Selected report comparison"
        subtitle={`${records.length} selected experiment records`}
        action={
          <div className="actions">
            <button
              disabled={!records.length}
              onClick={() => download('ledgershield-experiments.json', records)}
            >
              Export JSON
            </button>
            <button
              disabled={!records.length}
              onClick={() => download('ledgershield-episode-results.csv', rows, true)}
            >
              Export episode CSV
            </button>
            <button disabled={!records.length} onClick={() => setSelected({})}>
              Clear selection
            </button>
          </div>
        }
      >
        {records.length ? (
          <>
            <div className={`notice ${matched ? 'information' : 'warning'}`}>
              {matched
                ? 'Selected runs share evaluation seeds, episode counts and horizon. Inspect model status and reward configuration before drawing conclusions.'
                : 'Select at least two runs with matching seeds, episode counts and horizon for a fair comparison. These rows alone do not establish improvement.'}
            </div>
            <BarChart
              rows={records}
              nameKey="actual_policy"
              title="Mean episode rewards of selected experiments"
            />
            <Table
              rows={records}
              columns={[
                {
                  label: 'Policy / run',
                  render: (r) => (
                    <>
                      {label(r.actual_policy)}
                      <small className="cell-note">{short(r.id)}</small>
                    </>
                  ),
                },
                { label: 'Mean reward', render: (r) => number(r.mean_reward, 3) },
                {
                  label: 'Reward sample SD',
                  render: (r) =>
                    standardDeviation(r.results) === null
                      ? 'N/A · one episode'
                      : number(standardDeviation(r.results), 3),
                },
                {
                  label: 'Committed transfers',
                  render: (r) =>
                    r.results.reduce((sum, row) => sum + row.metrics.committed_transactions, 0),
                },
                {
                  label: 'Recoveries',
                  render: (r) => r.results.reduce((sum, row) => sum + row.recoveries, 0),
                },
                {
                  label: 'Configuration',
                  render: (r) => (
                    <details>
                      <summary>Inspect configuration</summary>
                      <pre>
                        {JSON.stringify(
                          {
                            seed: r.seed,
                            episodes: r.episodes,
                            horizon: r.horizon,
                            ...r.environment_config,
                          },
                          null,
                          2,
                        )}
                      </pre>
                    </details>
                  ),
                },
              ]}
            />
            <p className="chart-note">
              Rewards are toy-simulator measurements, not security guarantees. Bar length shows
              reward magnitude; numeric labels preserve sign. Standard deviation describes variation
              across the recorded scenarios, not a confidence interval.
            </p>
          </>
        ) : (
          <Empty title="No experiments selected">
            Run a matched comparison or select records in the registry. Exports contain only the
            selected measured results.
          </Empty>
        )}
      </Panel>
      {detail && (
        <Details title={`Experiment / ${short(detail.id)}`} onClose={() => setDetail(null)}>
          <KeyValues
            entries={[
              ['Requested policy', label(detail.requested_policy)],
              ['Actual policy', label(detail.actual_policy)],
              ['Evaluation seed', detail.seed],
              ['Episodes', detail.episodes],
              ['Horizon', detail.horizon],
              ['Comparison group', detail.comparison_id || 'Independent evaluation'],
              ['Storage', 'In memory until process restart'],
            ]}
          />
          <LineChart
            rows={detail.results.map((r, i) => ({ ...r, episode: i }))}
            xKey="episode"
            yKey="reward"
            title="Evaluation episode reward"
          />
          <JSONDetails value={detail} title="Complete report and episode metrics" />
        </Details>
      )}
    </>
  )
}
