# Development, test and production-like operation

No cloud credentials or paid services are required. Native setup is documented in setup-guide.md. The simulator remains a centralized educational model in every mode.

## Local container demo

Generate local secrets with `python scripts/create_local_tokens.py`, then `docker compose up --build -d`. Default services: PostgreSQL 16, single backend worker, static built frontend through an unprivileged nginx reverse proxy. Backend runs Alembic before serving. PostgreSQL readiness gates API startup; API readiness gates frontend startup. Host ports are loopback 8000 (API) and 5173 (dashboard); PostgreSQL has no host port. Internal URLs use postgres:5432 and backend:8000. Docker must use a Linux engine.

`docker compose --profile monitoring up -d` adds Prometheus at localhost:9090 and provisioned Grafana at localhost:3001. Grafana user is ledger with generated GRAFANA_ADMIN_PASSWORD. Dashboard shows actual simulator block height, stalls, latency and recoveries. `--profile cache` adds internal Redis for future extensions; the current application does not use or require it.

`docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build` enables backend reload and Vite with source mounts. Native dev is simpler where filesystem watching is constrained. Default Compose is production-like static serving, not an Internet deployment. CI builds backend/frontend images separately and validates all Compose profiles.

## Data and lifecycle

postgres_data persists database research records. prometheus_data and grafana_data persist monitoring state. `docker compose down` stops/removes services but retains named volumes. Do not use `down -v` unless intentionally discarding records. Back up PostgreSQL with normal pg_dump/restore workflows and test restoration on a disposable database. Process shutdown cancels the tick loop, archives final public state and closes connections. Database failures reject readiness; archive failures pause the simulator and return explicit errors.

Snapshots, audit/healing records and completed experiments are durable. Restart restores completed experiment listings but initializes a fresh paused ledger; snapshots are historical evidence, not resumable consensus checkpoints. Native DATABASE_URL can use SQLite for a zero-service archive. Apply `alembic upgrade head` before native startup. Schema revision 0001 creates research_records; review migrations before database changes. No automatic destructive migration is performed.

## Secrets and exposure

POSTGRES_PASSWORD, LEDGERSHIELD_OPERATOR_TOKEN, LEDGERSHIELD_ADMIN_TOKEN and GRAFANA_ADMIN_PASSWORD must be generated and kept out of Git. Compose passes environment secrets for local development; container inspect/config output may expose resolved values, so do not publish it. Use URL-safe database passwords with the provided generator, or percent-encode special characters in DATABASE_URL. Optional deployment should inject credentials through a secret manager or protected environment, add TLS/identity/network policies, and rotate credentials. No automated public deployment is configured.

Containers drop application capabilities and run backend/static frontend as non-root. Redis/database are internal. This does not certify production security. Liveness `/live` is process-only; readiness `/ready` checks schema/database and chain integrity. Prometheus `/metrics` records simulator counters; values reset with simulator reset and should not be described as hardware benchmarks. Use one API worker because active simulator state and rate limits are process-local.
