# Backend API v1

OpenAPI: `/openapi.json`; interactive docs: `/docs` and `/redoc`. Live simulator state is in memory. Ledger batches execute atomically. Optional SQLAlchemy/Alembic database archives retain public research records; see the archive extension below. Reset clears the simulator's ledger, scenarios, evidence and recovery. Restart also clears experiments. The experiment store retains the latest 100 completed evaluations.

## Authentication and roles

Reads and read-only streams are public on loopback. Every mutation, including legacy aliases, requires `Authorization: Bearer <token>`. Generate distinct tokens with `python scripts/create_local_tokens.py`; start uvicorn with `--env-file .env`. The generator never prints tokens. The ignored `.env` stays local. Enter a token in the dashboard password field; it stays in React memory, never local/session storage or a URL.

Operators submit transactions, run/start/stop simulation, apply scenarios/partitions and evaluate policies. Admins additionally reset state, change recovery modes and approve actions. Tokens must be distinct and at least 32 characters. Missing configuration disables mutations (503); missing/invalid credentials return 401 with `WWW-Authenticate`; insufficient roles return 403. This is a two-principal local access model, not an Internet-facing identity/session system. TLS, identity-provider integration and token rotation/revocation remain deployment work.

Both services bind to loopback. Browser origins are restricted to localhost/127.0.0.1 ports 5173 and 8000. No permissive CORS or query credentials are used. WebSockets are read-only with at most 16 simultaneous connections. Do not expose development ports publicly.

## Endpoint contracts

All paths below have prefix `/api/v1`.

| Method | Path | Real state / operation | Role |
| --- | --- | --- | --- |
| GET | `/health` | Replays ledger integrity; running/storage status | Public |
| GET | `/metrics` | Typed JSON simulator/application metrics | Public |
| GET | `/network/overview` | Config, consensus, metrics, running state and mode | Public |
| GET | `/network/state` | Bounded dashboard snapshot | Public |
| GET | `/nodes` | Paginated participants/telemetry | Public |
| GET | `/nodes/{node_id}` | Public identity, behavior, trust and telemetry | Public |
| GET | `/blocks` | Paginated canonical chain, including genesis | Public |
| GET | `/transactions` | Paginated pending/committed/rejected signed transfers | Public |
| POST | `/transactions` | Validate/stage signed transfer; acceptance is not finality | Operator |
| GET | `/alerts` | Paginated detector evidence | Public |
| GET | `/trust/scores` | Paginated bounded scores and evidence counts | Public |
| GET | `/healing/actions` | Paginated recovery proposals/outcomes | Public |
| GET | `/healing/actions/{action_id}` | Full recovery record | Public |
| POST | `/healing/actions/{action_id}/approve` | Recheck expiry/guards and execute pending action | Admin |
| POST | `/healing/mode` | Change recovery mode | Admin |
| POST | `/simulation/scenarios` | Apply node behavior; record scenario ID/tick | Operator |
| POST | `/simulation/start` | Idempotently enable background loop | Operator |
| POST | `/simulation/stop` | Idempotently pause loop, preserving state | Operator |
| POST | `/simulation/step` | Run an explicit round | Operator |
| POST | `/simulation/transaction` | Sign/stage public simulator-wallet transfer | Operator |
| POST | `/simulation/partition` | Apply groups; empty groups clear partitions | Operator |
| POST | `/simulation/reset` | Validated new config; paused observe-only state | Admin |
| POST | `/policies/evaluate` | Bounded isolated evaluation; stores completed experiment | Operator |
| GET | `/experiments` | Paginated actual API-created evaluation records | Public |
| GET | `/experiments/{experiment_id}` | Actual policy, seeds, rewards and metrics | Public |

Collections return `{items,total,offset,limit,storage:"in_memory"}`. Defaults: offset 0, limit 20; maximum limit 100. Ordering is insertion order. Offset pagination is not a snapshot guarantee while the background loop changes state; pause for stable traversal.

Status codes: 200 reads/controls; 201 applied scenario/completed experiment; 202 mempool acceptance; 400 semantic protocol rejection; 401 unauthenticated; 403 forbidden role/origin; 404 missing resource; 409 duplicate/nonce conflict, non-pending approval or busy evaluation; 422 invalid input/pagination; 429 rate limit; 503 unavailable auth configuration, integrity failure or sanitized service failure. Approval workflows return explicit statuses such as expired, blocked quorum, cooldown or rollback; a 200 workflow response does not mean recovery succeeded.

Every HTTP response has `X-Request-ID` and `Cache-Control: no-store`. Safe 8–64 character incoming IDs are preserved; otherwise a UUID is generated. Errors use `{error:{code,detail,request_id}}`. Validation reports field locations without raw input. Unexpected errors return generic 503 responses. No private keys, tokens, exception text or stack traces are returned. JSON logs contain timestamp, request ID, method, route template, status and duration, excluding bodies, headers and query values.

## Bounded evaluation

Request: `{"policy":"rule","episodes":4,"horizon":10,"seed":20000}`. Policies: no_healing/rule/dqn; episodes 1–8; horizon 1–30; seed >=10000. Extra fields are rejected. DQN reads only a server-configured checkpoint path, never a caller path. Invalid/missing models report `actual_policy:"rule_fallback"`. No endpoint trains, replaces or deploys weights, invokes arbitrary code or changes the live ledger. Separate simulator instances produce per-episode seeds, rewards, recoveries and metrics. Single-policy evaluation does not establish improvement; the offline CLI compares matched baselines.

Limits: 60 mutations/minute per role; 3 evaluations/minute per role; one active evaluation per process; `Retry-After` accompanies 429. Evaluation runs in a worker thread with at most 240 environment steps. This is bounded local computation, not a process-level resource sandbox. Limits and records are per process; run one worker.

## WebSocket events

Connect to `/api/v1/ws`. Envelope: `{"type":"metrics","sequence":2,"timestamp":1,"data":{...}}`. Sequence increases per connection; timestamp is simulator tick. Snapshot supplies bounded dashboard state, then metrics follows. New alert IDs emit alert events; new/changed action statuses emit healing events. Reconnection replays currently visible latest 50 alerts/actions, not a durable log. Reset starts a new evidence set. Internal stream failures close with generic 1011. Legacy `/ws/dashboard` remains snapshot-only; legacy mutation aliases enforce the same roles.


## Phase 9 dashboard extensions

New public reads: `/auth/session` (viewer or authenticated role), `/trust/history` (paginated, exact node_id and q filters), `/audit/events` (latest 500), `/settings` (safe values), `/blocks/{height}` (payload plus integrity/certificate checks), `/learning/runs` (fixed server-owned training manifests and checkpoint metadata), `/simulation/runs` (actual bounded runs).

Operator mutations: `POST /simulation/runs` starts one supported fault for 1–20 ticks; `POST /simulation/runs/{run_id}/stop` restores fault settings and is idempotent after completion. `POST /policies/compare` runs isolated no-healing/rule/DQN comparisons with shared seeds, up to 4 episodes and 20 steps each. Existing evaluation lock and rate limits apply. Results include comparison group IDs and real environment/reward configuration. All existing role checks remain enforced.

Block, transaction, alert, healing-action and experiment lists accept server-side q filters. Snapshots add service instance ID, real metric history (240 samples), partition links, active scenario and recent events. Recovery records expose proposal mode, approval requirement and guard results captured at execution. See DASHBOARD.md for scope and lifecycle details.


## Archive and health extensions

GET /live reports process liveness; GET /ready checks chain integrity and the configured archive/schema. Optional DATABASE_URL enables transactional public snapshots, audit/healing records and experiments. GET /api/v1/archive/{snapshot,event,healing,experiment} reads up to 1000 archived rows through pagination. Completed experiment listings reload on restart; live collections stay in_memory and start a new paused simulation. Database write failure returns sanitized 503 archive_unavailable, pauses the loop and warns that the action may have completed in memory. No distributed memory/database atomicity is claimed. Migrate explicitly before startup.


## Re-audit changes

Archive kinds also include block, transaction, alert, trust and scenario. Pagination executes in the database and reports the complete count, replacing the prior 1000-row retrieval cap. Settings, archive pages and process/readiness probes have explicit public Pydantic response models. Healing records may include sanitized policy_error and failed attempt_metrics. Observe-only now blocks previously pending approval execution; expiry is reflected without clicking approval. Metrics add transport_elapsed_ms; production delay includes jitter and timeout waits.
