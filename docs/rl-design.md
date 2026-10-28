# Learning design

The live recovery service uses RulePolicy. Offline experiments use a NumPy 12→32→7 ReLU DQN, epsilon-greedy exploration, replay, discounted TD targets, clipped error gradients and target-network copies every 50 updates. No API route trains, replaces or deploys a model.

Gymnasium observations are normalized to [0,1]: availability, target trust, transaction acceptance, last consensus progress, latency, timeout rate, invalid-vote fraction, quarantine, increased monitoring, last action, elapsed horizon and stalls. Episodes truncate at the configured horizon; seeded reset creates reproducible transport/scenarios.

Actions: observe, monitor, quarantine, restore, resync, recommend reassignment and request view change. The guarded orchestrator rejects unsupported actions, unverified quarantine, loss of quorum and unsafe restoration. Missing/invalid checkpoint predictions fall back safely; model metadata distinguishes trained updates, no updates and missing/invalid checkpoints.

Default reward: +1 transaction progress, +.3 availability, +.5 consensus progress, -.2 normalized latency, +.5 verified mitigation, -1 intervention on honest target, -.05 unnecessary intervention, -.5 collateral lag and -.1 recovery duration. Terms are bounded [0,1] and RewardWeights exposes coefficients. Tests independently reconstruct the reward equation.

`python -m ledgershield.learning --episodes 40 --output artifacts/experiment` trains explicitly, saves JSON weights, reloads and evaluates no-healing/rule/DQN on separate seeds. Matching repeated runs are tested for identical parameters and results. Train/evaluation seed intervals cannot overlap. The small four-scenario family is insufficient to establish generalization. Published DQN results did not beat no healing; see experiments.md.
