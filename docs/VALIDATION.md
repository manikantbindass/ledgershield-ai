# Validation and refinement — 2026-10-28

See [requirement-by-requirement review](REQUIREMENTS_REVIEW.md) for implemented scope and remaining research/deployment limitations. Tests demonstrate checked behavior; they are not a guarantee of zero defects.

## Latest local checks

| Check | Actual result |
| --- | --- |
| Full backend regression suite | 123 passed; one upstream Starlette TestClient transport deprecation warning |
| Final changed-area API/archive/safety contracts | 37 passed after ordered snapshot metadata was added |
| Frontend suite | 30 passed across five files |
| Ruff lint and formatting | Passed for canonical backend, simulator, tests and migrations |
| Mypy | Passed for public Pydantic models and persistence, the declared strict scope |
| Frontend TypeScript / ESLint / Prettier / production build | Passed; strict TypeScript scope is the shared utility/API-boundary module |
| npm audit | Zero known vulnerabilities at the time checked |
| Compose default, monitoring/cache profiles and dev override | Configuration checks passed |
| Real application subprocess E2E | Included in backend suite: signed transfer, block certificate, fault/alert, pending decision, approved recovery and WebSocket state |
| Native live application | SQLite readiness, anonymous mutation 401, three committed transfers, three verified commit votes, approved recovery, complete archive pagination beyond 1000 rows, three event clients, 15 concurrent health reads and dashboard proxy passed |
| Existing demo history | 20,876 public research records preserved before restarting the local API |
| Matched application-level comparison | 36 actual runs completed with seeds 22000–22002, horizon 8, four scenarios and three policies; report includes implementation/checkpoint fingerprints |
| Owned README animations | Both tracked SVGs parse and contain animation elements; tests verify their README references |
| Screenshots / fresh browser visual QA | Pending by explicit user choice; local browser use is disabled in Work settings |

Actual native diagnostic values, including 15-read sample timing, are in [local-verification.json](reaudit/local-verification.json). These are local diagnostics, not production latency benchmarks. Full simulator comparison and raw samples are [JSON](experiments/resilience-comparison.json) and [CSV](experiments/resilience-runs.csv). Undefined measurements remain null, and conditional detection/recovery timing is labeled.

## Important corrections found by this review

The review fixed stale approval/mode and resync guards; valid-vote and serial transport delay accounting; noncanonical/malformed core input; missing complete trust/block archive history and redundant writes; unbounded stream deduplication/handshake slots; silent-stream and out-of-order frontend updates; and local RL training/evaluation provenance mixing. The dedicated regression tests retain these cases. A new archive pagination annotation initially shadowed the class's list method; type/import checks caught it and the corrected annotation passes the targeted suite. Snapshot validation also caught an incomplete test fixture (missing quorum); the fixture was corrected rather than weakening the production check.

Earlier QA found the PostgreSQL driver raises TypeError directly for invalid JSON while SQLite wraps it in StatementError. The test accepts these two specific behaviors and still verifies batch rollback. A one-second subprocess readiness probe was replaced by a bounded startup deadline. Cancellation handling preserves AbortError across JavaScript realms. No meaningful failure was converted into a skipped/pass result.

## CI and container evidence

[Baseline green CI af07684](https://github.com/manikantbindass/ledgershield-ai/actions/runs/40669811907) passed all seven jobs: backend tests/quality, PostgreSQL integration, frontend checks/build, Compose configuration and real container builds/startup/signed-ledger/approved-recovery/archive smoke testing. The refined workflow additionally starts monitoring/cache profiles, verifies actual Prometheus samples, provisioned Grafana panels and Redis PING. Final review-run status is available in [repository Actions](https://github.com/manikantbindass/ledgershield-ai/actions) and reported with task completion. Local Docker engine startup was unavailable; no local container run is claimed.

## Historical ML evidence and limitations

The recorded 40-episode training run performed 769 parameter updates. Its held-out mean rewards were 35.253 (no healing), 35.202 (rule), 34.253 (DQN), each with 240 committed evaluation transfers. The DQN did not outperform no healing. The synthetic detector's separate-seed evaluation counted 100 true positives, 20 false positives, 380 true negatives and zero false negatives. These are constructed toy distributions, not real-world detection accuracy or security benchmarks. See experiments.md for methods and sample/interval limitations.

Live consensus remains a centralized, volatile simulator. The archive is durable research evidence, not a resumable distributed state machine. Shared local bearer roles are not deployment identity management. Fresh desktop/tablet accessibility certification, real P2P, formal PBFT, independent security review and owner-selected licensing remain outstanding. No screenshot or license grant has been fabricated.
