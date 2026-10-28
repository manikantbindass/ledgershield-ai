# Local validation — 2026-10-28

Validated on Windows with Python 3.12.4 and Node 24.14.1. Commands ran from the repository root, except npm commands in `frontend`.

| Check | Result |
| --- | --- |
| `python -m pytest -q` | 60 tests passed, including versioned API, RBAC, pagination, rate limits, sanitized failures, events and prior ledger/simulator/learning regressions |
| `npm run lint` | Passed |
| `npm run build` | Passed, Vite 8.3.5 |
| `npm audit --audit-level=low` | Zero known vulnerabilities at validation time |
| `docker compose config --quiet` | Passed configuration validation; containers were not launched |
| Animated header/footer XML | Both SVG documents parsed successfully |
| `git diff --check` | Passed after source newline normalization |
| Running API/proxy | Versioned health and dashboard proxy returned 200; anonymous mutation returned 401 |
| Live workflow | Signed demo transfer committed; verified malicious-vote evidence produced an approval; approved quarantine recorded a verified recovery |
| Browser | Observatory connected to live telemetry; no browser console errors observed after API v1 integration |

The suite initially encountered sandbox temporary-directory and local async-client restrictions. Running it outside that restricted test environment completed successfully. One upstream Starlette warning notes a future TestClient HTTP transport migration from httpx; tests currently pass. HTTPX is only a test dependency. No remote CI outcome is claimed before GitHub runs the new workflow.

## Measured offline experiment

Executed `python -m ledgershield.learning --episodes 40 --output artifacts/experiment`. Training completed **769 parameter updates**, saved a checkpoint, reloaded it for evaluation and recorded 36 held-out episodes: 12 per policy, with matching seeds/scenarios. No evaluation episodes enter training.

| Policy | Mean episode reward | Total committed evaluation transfers | Verified recoveries |
| --- | ---: | ---: | ---: |
| No healing | 35.253 | 240 | 0 |
| Rule policy | 35.202 | 240 | 6 |
| DQN | 34.253 | 240 | 0 |

The DQN **did not outperform the no-healing baseline**. Each toy scenario alters one target node, leaving enough honest validators to commit; intervention can therefore cost reward without increasing throughput. These results establish that training, checkpointing and evaluation execute, not that the learned agent improves resilience. More difficult multi-fault scenarios, broader seeds and uncertainty estimates are needed before any improvement claim.

The synthetic Isolation Forest evaluation used seed 202, separate from normal-only fitting at seed 101: 100 true positives, 20 false positives, 380 true negatives and 0 false negatives across 500 labeled synthetic rows. Those labels and feature distributions were constructed for this experiment; this is not a real-world attack-detection benchmark. Detector confidence is heuristic, not calibrated probability.

Machine-readable results and all training episode rewards are in [measured-results.json](experiments/measured-results.json). Full generated experiment records, CSV datasets and model checkpoint remain ignored under `artifacts/` and can be recreated with the documented commands.

## Scope limits

Everything is a local, centralized simulator with volatile state. Auth provides two local roles, not deployment identity management. No database persistence/migrations, real P2P, full PBFT view-change proof, production security, automatically deployed RL policy or online learning is claimed. Docker execution and remote GitHub Actions results are unverified in this local validation. Screenshots are deferred until the user's final phase.


## Phase 9 validation

The expanded backend suite passes 72 tests. The new frontend suite passes 22 tests; frontend lint and production build pass. Scenario tests cover all six kinds, bounded expiry, restored settings, fixed membership, conflicts and real API comparison records. Frontend tests cover ten routes and operational workflows including permissions, filters, pagination, approvals, comparisons, themes and offline states. See DASHBOARD.md for visual-check coverage and limitations. CI now includes frontend tests.


Latest QA additions: the complete 80-test backend suite passed, seven reward/horizon boundary checks passed, three matched-runner tests passed, and all 25 frontend tests passed. Scoped Python/TypeScript checks, Ruff/Prettier formatting, frontend lint/build, Compose profile/config validation and npm audit (zero known vulnerabilities) passed. The initial process-E2E startup probe failed with a one-second read timeout; a bounded readiness deadline fixed it and the full backend suite then passed. The cancellation error test also found and fixed cross-realm AbortError handling. No test was skipped to obtain these results. Docker Desktop did not provide a working local Linux engine; actual image/stack/PostgreSQL verification is assigned to the explicit CI jobs and is not claimed locally.
