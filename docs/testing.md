# Testing and quality gates

Install `requirements-dev.txt` and `npm ci` in frontend. Run from repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check backend ledgershield tests migrations
.\.venv\Scripts\python.exe -m ruff format --check backend ledgershield tests migrations
.\.venv\Scripts\python.exe -m mypy
cd frontend
npm run lint
npm test
npm run typecheck
npm run format:check
npm run build
```

Unit tests cover canonical hashing/signatures, transaction/block validation, replay/conflict rejection, atomic state, trust bounds/decay, detector rules, observations/reward terms and policy safeguards. Integration tests exercise API/service, authorization, pagination, sanitized failures, signed consensus, WebSocket events, detection-to-healing, synchronization and isolated experiments.

Database tests run Alembic against fresh SQLite files, verify transactional rollback, reopen/restart archives, retained experiment records, visible failures and missing-migration startup rejection. Set TEST_DATABASE_URL to a disposable PostgreSQL database to run the same tests against PostgreSQL; never point tests at a valuable database. CI has a dedicated PostgreSQL service job.

The process E2E starts a real uvicorn subprocess on a free loopback port, initializes network state, signs/submits a transfer, verifies a block, simulates a malicious vote, checks alert/proposal, approves quarantine and verifies the resulting API/dashboard WebSocket snapshot. The subprocess is cleaned up even on failure. Frontend tests separately exercise the dashboard with explicitly synthetic test-only fixtures: routes, forms, approvals, filters, pagination, losses, comparisons, exports, themes and offline states. This combination is not a claim of a full browser-driven authenticated E2E run.

ML tests repeat complete training/checkpoint/evaluation runs, compare parameters/results, enforce evaluation separation, reconstruct rewards and validate bounded observations/actions. Synthetic row splits use independent seeds; no evaluation rows are fitted.

Ruff lint/format covers canonical backend/simulator, migrations and tests. Mypy strict function annotations cover public Pydantic models and transactional persistence; the remaining Python code is not claimed fully statically typed. TypeScript checks shared frontend data/export/API-boundary utilities; JSX views are covered by ESLint, tests and production compilation. Prettier formats frontend source/tests/config. Legacy research helpers have not been silently certified by these gates. Failures remain CI failures; no continue-on-error or blanket exception suppression is used to pass checks.
