# Troubleshooting

- Dashboard offline: check native API on 127.0.0.1:8000/ready and Vite on 5173, or Compose health/status. The stale-data banner deliberately disables mutations. Read request IDs in Settings & Audit; do not paste credentials into reports.
- 401/403: verify the correct token in Settings. Operators cannot reset, change recovery mode or approve. Empty auth config gives 503. Tokens need 32+ characters and distinct roles. Theme storage never stores credentials.
- 429: honor Retry-After; evaluations have a separate 3/minute limit and one concurrent job. Refreshing the page does not bypass server limits.
- Scenario already active: stop its run or let bounded rounds expire. Pausing prevents expiry progress; manual steps still advance. Stop restores fault settings, not committed history or recovery quarantine.
- Consensus stalls: check available validators, partitions and timeout/latency. Restore enough honest reachable validators; never lower quorum. A fixed four-validator network needs three valid votes.
- Missing migrations: set DATABASE_URL in the same terminal, run Alembic upgrade head, then restart. API refuses unmigrated schema rather than silently resetting data.
- Archive unavailable: service may have changed in memory before storage failed. Simulation pauses; inspect state before retrying. Restore DB connectivity and check readiness. SQL/driver errors and secret paths are not returned to clients.
- Docker engine missing: start Docker Desktop with its Linux engine and inspect docker context ls. Windows-container mode cannot run these Linux images. Do not claim Compose succeeded if only config validation ran.
- Database credential changed with existing volume: PostgreSQL image initialization variables do not rotate an existing role password. Rotate explicitly through an authorized DB workflow; never delete the volume to hide the mismatch.
- RL report missing: run the offline training CLI. RL Lab labels missing checkpoint separately from historical training data. Missing DQN uses explicit rule_fallback in evaluation. No API startup trains automatically.
- Tests cannot create temp files or open loopback sockets: use a permitted test workspace/runner and explicit pytest --basetemp under artifacts. Do not skip failing tests to claim success.
- Screenshots: final README captures remain deferred until final-phase approval. Existing figures and experiment summaries are actual measurements, not fabricated UI screenshots.
