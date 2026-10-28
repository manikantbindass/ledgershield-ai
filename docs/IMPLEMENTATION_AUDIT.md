# Initial audit — 2026-10-28

Inspected every tracked source and configuration file on main at f8812bf before modifications.

Working foundations: FastAPI routes and WebSocket, React 19/Vite 8 dashboard, SHA-256 hashing, basic in-memory ledger, bounded trust helper, Isolation Forest wrapper, NetworkX clique heuristic and PyTorch actor/critic.

Gaps: API streams random mock data; no DB, Kafka client, authentication, signed verification, telemetry or recovery orchestration is connected. Ledger accepts overspending, duplicate/unsigned transactions and altered blocks. Consensus permits undersized networks and counts unverified vote keys. Trainer imports nonexistent rl_agent package, updates only critic, has no PPO loss or seeded evaluation. No tests or root ignore file exist. README claims absent security and production readiness. Tailwind 4 uses incompatible v3 PostCSS configuration; Docker Node 18 is too old for Vite 8. Old scientific pins conflict with local Python 3.14; Python 3.12 is available. Compose contains fixed development credentials. Attack script sends traffic, not a protocol Sybil attack.

Preserve existing research helpers and dashboard; introduce a canonical ledgershield package, signed integer transfers, atomic execution, seeded simulator, telemetry, evidence and guarded local recovery. No real P2P or formal Byzantine safety claim. Durable storage/authentication remain future work. Results are recorded in VALIDATION.md.


Follow-up phases retain this initial baseline record. The canonical runtime now has signed state execution, bounded simulator recovery, versioned local authorization, ten dashboard pages, a transactional optional research archive, Alembic migration, layered QA and container/monitoring configuration. Historical gaps above are findings at f8812bf, not a claim about current implementation. See architecture.md, DASHBOARD.md and testing.md for actual scope; durable live consensus resumption and production deployment remain unimplemented.
