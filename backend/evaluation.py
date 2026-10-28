"""Bounded evaluation in isolated simulator instances. Never trains or deploys a model."""
from datetime import datetime, timezone
import os
from uuid import uuid4
from ledgershield.learning import HealingEnv, baseline_action, load_policy


def evaluate(payload):
    actual = payload.policy
    if payload.policy == "dqn":
        # Server-owned path only; callers cannot read arbitrary filesystem paths.
        policy, actual = load_policy(os.getenv("LEDGERSHIELD_MODEL_PATH", "artifacts/experiment/dqn.json"))
    elif payload.policy == "rule":
        policy = baseline_action
    else:
        policy = lambda _: 0
    env = HealingEnv(horizon=payload.horizon)
    rows = []
    for i in range(payload.episodes):
        obs, _ = env.reset(seed=payload.seed + i, options={"scenario": i % 4})
        reward_total = 0
        for _ in range(payload.horizon):
            obs, reward, _, _, info = env.step(policy(obs))
            reward_total += reward
        rows.append({"seed": payload.seed + i, "scenario": i % 4,
                     "reward": reward_total, "recoveries": info["recoveries"], "metrics": info["metrics"]})
    return {"id": str(uuid4()), "status": "completed", "requested_policy": payload.policy,
            "actual_policy": actual, "seed": payload.seed, "episodes": payload.episodes,
            "horizon": payload.horizon, "mean_reward": sum(r["reward"] for r in rows) / len(rows),
            "results": rows, "created_at": datetime.now(timezone.utc).isoformat(),
            "storage": "in_memory", "scope": "local_simulator_evaluation"}
