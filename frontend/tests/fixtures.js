export function fixture() {
  const metrics = {
    height: 1,
    view: 0,
    stalls: 0,
    throughput: 1,
    committed_transactions: 1,
    rejected: 0,
    message_latency_ms: 20,
    timeouts: 0,
    participation: 1,
    voting_consistency: 1,
    availability: 1,
    anomalies: 2,
    recovery_successes: 0,
    recovery_failures: 0,
    simulated_seconds: 1,
    blocks: 1,
  }
  const nodes = Array.from({ length: 6 }, (_, i) => ({
    id: `node_${i}`,
    identity: String(i).repeat(64),
    validator: i < 4,
    status: 'honest',
    behavior: 'honest',
    quarantined: false,
    monitoring: false,
    height: 1,
    trust_score: 80,
    telemetry: {
      attempts: 4,
      timeouts: 0,
      votes: i < 4 ? 2 : 0,
      invalid_votes: 0,
      latency_ms: 20,
      valid_transactions: 0,
      invalid_transactions: 0,
    },
  }))
  const transaction = {
    sender: 'a'.repeat(64),
    receiver: 'b'.repeat(64),
    amount: 1,
    nonce: 0,
    chain_id: 'ledgershield-local',
    signature: '0'.repeat(128),
  }
  const alerts = [
    {
      id: 'alert-high',
      node_id: 'node_1',
      timestamp: 1,
      method: 'invalid_signed_vote',
      severity: 'high',
      confidence: 0.99,
      verified: true,
      features: [0.5, 0, 0.1],
      anomaly_score: -0.2,
      evidence: nodes[1].telemetry,
      explanation: 'Verified simulated wrong-hash vote',
    },
    {
      id: 'alert-medium',
      node_id: 'node_0',
      timestamp: 1,
      method: 'isolation_forest',
      severity: 'medium',
      confidence: 0.6,
      verified: false,
      features: [0, 0.4, 0.1],
      anomaly_score: -0.1,
      evidence: nodes[0].telemetry,
      explanation: 'Unverified synthetic indicator',
    },
  ]
  const actions = [
    {
      id: 'action-1',
      node_id: 'node_1',
      action: 'quarantine',
      timestamp: 1,
      evidence: alerts[0],
      trust: 65,
      expected_impact: 'quarantine',
      before: metrics,
      status: 'pending_approval',
      after: null,
      attempt: null,
      collateral_nodes: [],
      duration_ticks: null,
      reason: null,
      approval_required: true,
      proposed_mode: 'approval_required',
      safety_checks: { execution_guards: 'not_yet_evaluated' },
    },
  ]
  const config = {
    seed: 42,
    node_count: 6,
    validator_count: 4,
    latency_ms: 20,
    jitter_ms: 10,
    loss: 0,
    timeout_ms: 200,
    max_views: 4,
  }
  const blocks = Array.from({ length: 15 }, (_, index) => ({
    index,
    hash: `${index}`.padStart(64, '0'),
    previous_hash: '0'.repeat(64),
    timestamp: index,
    transactions: index === 1 ? [transaction] : [],
    validator: index ? 'node_0' : 'genesis',
    merkle_root: 'c'.repeat(64),
  }))
  const events = [
    {
      id: 'event-1',
      kind: 'consensus',
      timestamp: 1,
      summary: 'Block committed',
      details: { height: 1 },
    },
  ]
  const snapshot = {
    instance_id: 'test-service',
    nodes,
    config,
    metrics,
    mode: 'approval_required',
    running: false,
    history: [metrics],
    consensus: { committed: true, votes: 4, height: 1 },
    alerts,
    recovery: actions,
    partitioned_links: [],
    active_scenario: null,
    recent_events: events,
  }
  return { snapshot, blocks, transaction, alerts, actions, events, runs: [], experiments: [] }
}

export function server(data) {
  return async (url, options = {}) => {
    const parsed = new URL(url, 'http://localhost')
    const path = parsed.pathname.replace('/api/v1', '')
    const body = options.body ? JSON.parse(options.body) : {}
    const respond = (value, status = 200) => ({
      ok: status < 400,
      status,
      headers: { get: () => 'test-request' },
      json: async () => structuredClone(value),
    })
    const paginate = (rows) => {
      const q = (parsed.searchParams.get('q') || '').toLowerCase()
      rows = rows.filter((row) => JSON.stringify(row).toLowerCase().includes(q))
      const offset = Number(parsed.searchParams.get('offset') || 0),
        limit = Number(parsed.searchParams.get('limit') || 20)
      return respond({
        items: rows.slice(offset, offset + limit),
        offset,
        limit,
        total: rows.length,
      })
    }
    if (path === '/auth/session')
      return options.headers?.Authorization?.includes('admin-test')
        ? respond({ role: 'admin', permissions: ['configure'] })
        : respond(
            {
              error: {
                detail: 'Invalid local token',
                code: 'invalid_credentials',
                request_id: 'test-request',
              },
            },
            401,
          )
    if (options.method === 'POST') {
      if (path === '/healing/mode') data.snapshot.mode = body.mode
      if (path === '/simulation/start') data.snapshot.running = true
      if (path === '/simulation/stop') data.snapshot.running = false
      if (path.endsWith('/approve')) data.actions[0].status = 'recovered'
      if (path === '/simulation/reset') data.snapshot.instance_id = 'reset-service'
      if (path === '/simulation/runs') {
        const run = {
          id: 'scenario-1',
          ...body,
          started_at: 1,
          expires_at: 1 + body.duration_rounds,
          ended_at: null,
          status: 'running',
          details: {},
          scope: 'controlled_simulation',
        }
        data.snapshot.active_scenario = run
        data.runs.push(run)
        return respond(run, 201)
      }
      if (path.endsWith('/stop') && path.includes('/runs/')) {
        data.runs[0].status = 'stopped'
        data.snapshot.active_scenario = null
        return respond(data.runs[0])
      }
      if (path === '/policies/compare') {
        const records = ['no_healing', 'rule', 'dqn'].map((policy, i) => ({
          id: `run-${i}`,
          ...body,
          status: 'completed',
          requested_policy: policy,
          actual_policy: policy,
          comparison_id: 'comparison-1',
          created_at: '2026-10-28T00:00:00Z',
          mean_reward: i + 1,
          environment_config: { validator_count: 4 },
          results: [
            {
              seed: body.seed,
              scenario: 0,
              reward: i + 1,
              recoveries: 0,
              metrics: data.snapshot.metrics,
            },
          ],
        }))
        data.experiments.push(...records)
        return respond({ id: 'comparison-1', experiments: records })
      }
      return respond({ status: 'ok' })
    }
    if (path === '/network/state') return respond(data.snapshot)
    if (path === '/health')
      return respond({
        status: 'ok',
        integrity: true,
        running: data.snapshot.running,
        storage: 'in_memory',
      })
    if (path === '/settings')
      return respond({
        trust: {
          initial: 80,
          minimum: 0,
          maximum: 100,
          threshold: 40,
          decay: 0.01,
          violation_weight: 15,
          detector_weight: 0.5,
        },
        recovery: { mode: data.snapshot.mode },
        network: data.snapshot.config,
      })
    if (/^\/blocks\/\d+$/.test(path))
      return respond({
        block: data.blocks[Number(path.split('/').at(-1))],
        hash_valid: true,
        parent_valid: true,
        state_integrity: true,
        consensus: 'verified',
      })
    if (path === '/blocks') return paginate(data.blocks)
    if (path === '/transactions')
      return paginate([
        {
          tx_hash: 'tx-1-abcdef123456789',
          transaction: data.transaction,
          status: 'committed',
          submitted_at: 0,
          committed_at: 1,
        },
      ])
    if (path === '/alerts') return paginate(data.alerts)
    if (path === '/healing/actions') return paginate(data.actions)
    if (path === '/healing/actions/action-1') return respond(data.actions[0])
    if (path === '/trust/history')
      return paginate([
        {
          node_id: parsed.searchParams.get('node_id'),
          evidence_id: 'evidence-1',
          timestamp: 1,
          before: 80,
          decayed: 80,
          after: 80.2,
          delta: 0.2,
          kind: 'participation',
          confidence: 1,
          verified: true,
          provenance: 'simulator',
        },
      ])
    if (path === '/simulation/runs') return paginate(data.runs)
    if (path === '/audit/events') return paginate(data.events)
    if (path === '/experiments') return paginate(data.experiments)
    if (path === '/learning/runs')
      return respond({
        run_id: 'recorded-test-run',
        source: 'Synthetic test fixture only',
        updates: 10,
        model: { status: 'trained', updates: 10, architecture: [12, 32, 7] },
        training: [
          { episode: 0, reward: 1, loss: 0.5 },
          { episode: 1, reward: 2, loss: 0.25 },
        ],
        evaluation: [
          {
            policy: 'no_healing',
            mean_reward: 1,
            episodes: 2,
            committed_transactions: 2,
            recoveries: 0,
          },
        ],
        claim: 'Test evidence only',
      })
    return respond({ error: { detail: 'Unknown fixture route', code: 'not_found' } }, 404)
  }
}
