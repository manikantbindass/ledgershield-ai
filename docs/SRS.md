# Software requirements specification

LedgerShield is a local research system for authenticated transfers, fault simulation, explainable evidence and guarded recovery. Users are viewers, operators and admins. There are no real funds, external validators or cloud prerequisites.

## Functional requirements

- Validate Ed25519 signatures, chain IDs, positive integer amounts, sequential nonces and balances. Reject duplicates/conflicts atomically. Hash canonical ordered blocks and verify replay from configurable genesis.
- Simulate fixed validator membership, authenticated prepare/commit votes, deterministic transport/faults, bounded view replacement and recorded stalls without reducing quorum.
- Collect real simulator metrics, rule/model indicators, bounded trust changes and evidence provenance. Quarantine needs verified evidence and preserved available quorum.
- Default to observe-only; provide approval and autonomous-local modes with idempotency, cooldown, retries, verification and rollback.
- Expose documented typed APIs, protected mutations, bounded isolated evaluations and read-only events. Present ten responsive dashboard views with honest loading/offline/error states and measured exports.
- Archive public snapshots, audit/healing records and completed experiments transactionally when DATABASE_URL is configured. Never archive private keys/tokens. Restore experiment listings on restart; start a fresh paused simulator.

## Quality and operational requirements

Seeded tests, distinct evaluation data, model checkpoint compatibility, local-only secrets, predictable error envelopes, structured request logs, liveness/readiness, migrations, persistent database volumes, CI tests/checks/builds and documented limits. No model training/deployment on API startup. No real-world Byzantine safety or improvement claim without evidence.

Acceptance evidence is in testing.md and VALIDATION.md. Durable live consensus resumption, production identity management, multi-worker coordination, full PBFT view-change proofs and real P2P remain outside implemented scope.
