# Security model and limits

Assets: transaction integrity, canonical ordering, fixed quorum, evidence provenance, API tokens and research-record integrity. Threat simulations include unavailability, transport faults, wrong-hash votes, correlated observer identities and conflicting transfers. They are controlled local demonstrations, not penetration-test evidence.

Ed25519 authenticates transfers and votes; canonical JSON, genesis binding, Merkle roots, nonces and atomic balance execution protect the simulated ledger. Reproducible demo keys are public and never suitable for wallets. Hash chaining does not independently prevent double spending.

Public loopback reads expose telemetry. Mutations require distinct operator/admin bearer tokens (minimum 32 characters). Admin controls reset/mode/approval. Browser origins are restricted; tokens stay in memory, never URLs/storage. Logs omit request bodies, headers, secret values and query text. Unexpected errors are sanitized; validation does not echo raw input. API rate limits and evaluation lock are per-process; only one worker is supported.

Recovery starts observe-only. Verified evidence and available quorum gate quarantine. Unverified detector signals cannot permanently ban participants. Cooldowns, retry limits, idempotency, expiry, consensus verification and rollback constrain local actions. No shell, credentials or external integrations are exposed to policy actions.

Database archives contain only public snapshots/audits and experiment records. Credentials and signing key objects are excluded. Runtime state can mutate before a later archive write fails; this returns explicit 503 with an ambiguous-outcome warning and pauses simulation. Callers must inspect state before retrying. There is no distributed transaction between volatile simulator and DB.

Containers use non-root application users where practical, restricted capabilities, internal database ports and loopback host publishing. `.env` is a local development convenience, not a production secret vault; inspect/back up it privately. Deployment needs TLS, real user identity/rotation, network controls, backup/retention policies and independent review. No production security certification is claimed. Legacy research helpers are excluded from the canonical runtime.
