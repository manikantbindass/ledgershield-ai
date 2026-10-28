# Phase 9 research dashboard

Ten hash-routed pages share the live simulator connection. All production measurements come from actual server state; frontend test fixtures are confined to tests.

| Page | Connected features |
| --- | --- |
| Overview | Consensus, throughput, delays, availability, participation, evidence/recovery feed, selectable series and up to 240 recorded metric samples |
| Network Explorer | Search/role filters, keyboard-selectable logical topology, configured unreachable links and participant identities/telemetry; graph draws at most 24 matching nodes while the directory keeps all matches |
| Blockchain Explorer | Server pagination/search, blocks and transfers, canonical payloads, hash/link/state replay and actual signature-certificate checks |
| Security Center | Searchable alert history, classifications, severity, heuristic confidence and evidence details |
| Trust Management | Participant-specific latest 100 audit records, timeline, component/decay contributions, thresholds, weights and provenance; bounded window explicitly labeled |
| Self-Healing Center | Searchable proposals, fault evidence, recorded execution guards, approvals, before/after outcomes, rollback and collateral effects |
| RL Lab | Server-owned offline reward/loss records, historical held-out results, export and checkpoint metadata separate from live policy |
| Simulation Lab | Authorized start/pause/step/transfers plus six bounded scenario kinds with actual expiry/stop/cleanup records |
| Experiment Reports | Matched no-healing/rule/DQN evaluations, explicit fallback labels, selectable comparison records, sample reward deviation, config and JSON/CSV exports |
| Settings & Audit | Token verification/clearing, authoritative role, safe configuration, integrity status, admin mode/reset, latest 500 server events and 20 tab-local diagnostics |

## Access and offline behavior

Public read-only access needs no token. Tokens verified through `/auth/session` remain only in tab memory; browser storage holds only theme preference. Operator/admin permission checks remain server-enforced. Viewer controls and operator access to admin controls are disabled. Reset requires form acknowledgment.

The shared WebSocket reconnects with bounded exponential backoff. Disconnection keeps the last snapshot under a stale-data banner with tick/time and disables mutations. Failed initial connection shows no substituted measurements. Resources abort requests on navigation and expose retry/error states. Successful actions refresh state and histories; diagnostics include sanitized request IDs. A changed service instance resets page-local selections.

Dark-first styling includes a light theme, desktop/tablet/mobile breakpoints, scrolling tables and mobile navigation. Semantic labels/table headers, keyboard focus, skip link, topology keyboard selection, chart sample sliders and exact data tables support accessible use. Reduced-motion preference is honored. System fonts and code-native icons avoid external asset dependencies.

## Bounded scenarios and research limits

One scenario is active at a time for 1–20 simulator ticks. Expiry is checked after application steps, including recovery-driven rounds. Starting enables the background loop; completion/stop restores its prior running state and fault configuration. Cleanup never rewinds blocks, pending transfers, trust evidence or recovery-driven quarantine.

- Node failure temporarily makes a participant unavailable.
- Delay configures global simulated latency up to 5000 ms.
- Partition splits validators deterministically and blocks cross-group links.
- Suspicious voting makes a selected validator sign the wrong proposal hash.
- Sybil-like behavior adds three temporary correlated **non-voting** observers; validator membership/quorum remain fixed. This is not a real-world Sybil defense benchmark.
- Conflicting transfers submit genuinely signed same-nonce transfers and report the actual rejection. Accepted transfers remain subject to consensus.

Matched evaluation uses at most 4 episodes × 20 steps × 3 policies with identical seeds/configuration. Missing DQN checkpoints explicitly use rule_fallback. Historical training evidence is separate from current checkpoint presence; the live policy remains rule-based. No training/deployment endpoint is added. Exports escape CSV quotes and spreadsheet formula prefixes.

## Validation and refinement

The current frontend suite passes 30 tests; the full backend suite passes 123 tests. Check VALIDATION.md for exact commands, declared type-check scope, real runtime results and CI evidence. Current live handling includes a ten-second snapshot watchdog, schema checks, monotonic revisions/service-instance ordering and explicit action-completed/state-refresh-failed reporting. Recorded policy guards and complete database archives are covered by regression tests.

A prior 506px light-theme visual inspection found no document-level horizontal overflow and caught a development stylesheet import issue, which was fixed through direct entry-point imports. Fresh desktop/tablet/browser certification is not claimed: local browser access is disabled, and the user explicitly chose to leave README screenshots pending. No mock screenshot is substituted.
