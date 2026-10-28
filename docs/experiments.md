# Reproducible experiments

## Application-level matched resilience runner

After explicit training, run `python -m ledgershield.experiments --checkpoint artifacts/experiment/dqn.json --seeds 22000 22001 22002 --horizon 8 --output artifacts/benchmark`. The runner requires a checkpoint with actual parameter updates and its adjacent experiment.json training-seed manifest. It rejects overlapping evaluation seeds and never silently substitutes a rule policy for trained RL.

It compares no automated healing, rule recovery and trained DQN through the same real Service detection/trust/guarded-recovery pipeline. All policies share network config, seed, two honest warm-up rounds, fault target, scenario and application horizon. Four scenario classes are normal, unavailable node, wrong-hash malicious voting and faulty abstention. The DQN observation adapter uses the trained environment's normalized layout; alert-triggered application evaluation is a distinct distribution from training and that limitation is recorded.

report.json and runs.csv include transaction throughput per simulated second, submit-to-commit latency, mean availability, completion rate including recovery verification rounds, labeled fault precision/recall/FPR, verified malicious-vote attack precision/recall, time to detect/recover, unnecessary interventions and failed attempts. Confusion counts are per-node per-episode. Undefined denominators and undetected/unrecovered timing are null, not invented zeros. Timing means are conditional on successful detection/recovery; inspect censoring flags/counts. Measures are simulated, not wall-clock hardware benchmarks.

Reports include raw rows, sample sizes, sample variance and exploratory seeded bootstrap 95% intervals when at least five observations exist. These intervals describe the sampled scenario mixture, not security guarantees. No superiority is asserted from the existence of an RL model. Generated model weights and raw working artifacts stay ignored; any published report is an actual measured run.

Run `python scripts/generate_dataset.py` for labeled synthetic train/evaluation CSVs and an evaluation confusion record. Seed 101 generates training rows; only normal rows fit Isolation Forest. Seed 202 generates evaluation rows. Tests verify repeatability and disjoint rows. Synthetic distribution performance is not real-world accuracy.

Run `python -m ledgershield.learning --episodes 40 --output artifacts/experiment` for offline DQN updates, checkpoint/reload, history and identical-seed no-healing/rule/DQN comparisons. Generated files are ignored by Git. Published measured summaries remain in docs/experiments/measured-results.json; no fresh values are invented when artifacts are missing.

The recorded 40-episode run made 769 updates. Twelve held-out episodes per policy yielded mean rewards 35.253 (no healing), 35.202 (rule), 34.253 (DQN). Each committed 240 transfers; rule recovered six times. DQN did not outperform baseline. The toy single-fault family often leaves sufficient quorum without intervention. Broader multi-fault scenarios and repeated seed families are needed for generalization/uncertainty claims.

Simulation Lab supports bounded reversible node failure, delays, partition, suspicious voting, non-voting Sybil-like identities and genuine same-nonce conflicts. Reports run isolated matched evaluations with actual policy/fallback, seeds, horizon, reward config, IDs and episode metrics. Select matching configurations before comparing. Exports preserve actual numbers; CSV fields escape formula prefixes. Standard deviation describes observed scenario variation, not a confidence interval.


The actual 36-run application comparison for evaluation seeds 22000–22002 and horizon 8 is published as [full JSON](experiments/resilience-comparison.json) and [raw CSV](experiments/resilience-runs.csv). These records contain actual measured results, per-policy sample sizes and limitations; no weights or credentials are included.
