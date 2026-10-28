# Requirement review and refinement

Reviewed against the supplied mission, blockchain/simulator/detection/trust/RL/recovery brief, API contract, dashboard, QA/deployment/documentation phases, and experiment-runner brief. This is a research implementation review, not a certification of zero defects.

| Requirement group | Implemented and checked | Limits / remaining work |
| --- | --- | --- |
| Repository and foundation | Original history retained; ledgershield-ai remote/main; owned README animations; env template, local secret generation, ignore rules, dependencies and CI | License remains the owner's decision; no license grant fabricated |
| Blockchain | Canonical Ed25519 transfers, positive integer units, nonces, atomic balances, duplicates/conflicts, ordered Merkle blocks, genesis binding and integrity replay | No real assets or production wallet/key infrastructure |
| Consensus/network | Fixed membership, signature-verified prepare/commit, quorum, seeded loss/latency/partitions, leader replacement, stalls and observer propagation | Centralized simulator, not full distributed PBFT; real P2P/independent replica proofs are not implemented |
| Telemetry/detection | Real counters and seeded transport waits; rules + reproducible Isolation Forest baseline; evidence/confidence, deduplication and independent evaluation data | Baseline detector fits normal synthetic rows at service creation; confidence is heuristic and synthetic results do not establish real-world attack accuracy |
| Trust | Bounded evidence weights, decay, duplicate protection, provenance and complete archived update records | Advisory scoring; no formal reputation-security proof |
| Recovery | Observe-only default, configured approvals, permitted actions, quorum/evidence/cooldown/retry guards, rollback, outcomes, failed-attempt diagnostics and mode rechecks | Autonomous disruption is simulator-only; reassignment is a recommendation; rollback cannot undo a real external system |
| RL | Seeded Gymnasium contract, bounded rewards/actions, real DQN updates/replay/target/checkpoints, explicit offline training and held-out baselines | Live API policy is rule-based. Historical/trained/missing model states are distinguished; no automatic DQN deployment or improvement claim |
| API | All 17 target routes, Pydantic contracts, pagination/search, role checks, rate limits, request IDs, sanitized errors and WebSocket events | Two shared local roles, one process; no deployment identity provider, public-network auth/TLS or multi-worker state coordination |
| Storage | Alembic + SQLAlchemy, PostgreSQL and native SQLite; atomic archive writes; public blocks/transfers/alerts/trust/scenarios/healing/events/snapshots/experiments retained with database pagination | Restart restores experiment listings but starts a fresh paused simulator. Archived history is not a resumable live-consensus checkpoint |
| Dashboard | Ten working routes, measured charts/detail records, filtering/pagination/forms/exports, permissions, light/dark/responsive layouts, loading/empty/error/success/offline states | JSX is not a full TypeScript rewrite; shared utilities are typed. Local browser access is disabled, so fresh visual/accessibility/device certification and README screenshots remain pending by user choice |
| Experiments | Actual matched no-healing/rule/trained-DQN runner; throughput, simulated latency, availability/completion, labeled detection, timing, interventions/failures, n/variance/exploratory intervals and implementation fingerprint | Narrow fault family, simulator timing and conditional detection/recovery timing. RL has not demonstrated superiority |
| QA | Layered units, integration, process E2E, persistence/restart/rollback, ML repeatability, frontend workflows; Ruff/Prettier/mypy/TypeScript/lint/build gates | Python strict typing covers public models/persistence; frontend strict typing covers shared utilities. Actual browser-driven E2E is not claimed |
| Containers/monitoring | Non-root app images, internal PostgreSQL, volumes, health gates, local secrets, optional Redis and provisioned Prometheus/Grafana; CI builds and runs stack | Redis is configured but unused by the app. Local Docker engine is unavailable; CI provides Linux runtime evidence. No public/cloud deployment performed |
| Documentation | Complete requested document set and evidence links; old initial audit retained as historical findings | No fabricated screenshots, license, benchmark/security guarantees or test outcomes |

## Defects corrected in this review

- A pending approval cannot execute after switching to observe-only. Pending records expire as ticks advance; removed targets are handled explicitly.
- Resync requires delivered communication from a reachable validator and a current target height after verification.
- Failed recovery retains attempted metrics before rollback. Policy exceptions are visible as sanitized fallback metadata.
- Consensus reports valid signatures rather than all submitted vote keys. Production-delay measurement includes seeded jitter and timeout waits.
- Core rejects malformed genesis/index/key/signature encodings; detector validates incoming features and non-finite config.
- Voting scenarios require validators. Temporary observer identities are reproducible without acquiring quorum membership.
- The archive persists complete collections, not only snapshot tails; unchanged records avoid redundant SQL writes, and failed writes never enter its success cache.
- Socket handshake failure releases its slot; per-connection deduplication stays bounded. Unexpected stream errors are surfaced through a generic 1011 close.
- Frontend watchdog marks silent streams stale, rejects malformed snapshots and orders revisions/service instances; delayed initial HTTP cannot overwrite a newer stream update; successful mutations with a failed follow-up fetch are not mislabeled as failed execution.
- RL Lab uses the selected local report's own evaluation results instead of mixing another run's published comparison.

The latest commands, measured results and CI links are maintained in VALIDATION.md. Screenshots remain pending after the user's explicit choice to continue without enabling browser access.
