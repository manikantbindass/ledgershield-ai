"""Read fixed server-owned experiment manifests; never expose paths or model weights."""

import json
import os
from pathlib import Path

from ledgershield.learning import DQN

ROOT = Path(__file__).resolve().parents[1]


def learning_report():
    model = {
        "status": "missing_or_invalid",
        "updates": 0,
        "architecture": [12, 32, 7],
        "live_policy": "rule",
        "automatic_deployment": False,
    }
    try:
        checkpoint = DQN.load(
            os.getenv("LEDGERSHIELD_MODEL_PATH", str(ROOT / "artifacts/experiment/dqn.json"))
        )
        model.update(
            status="trained" if checkpoint.updates > 0 else "untrained",
            updates=checkpoint.updates,
            architecture=[12, len(checkpoint.b1), 7],
        )
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        pass
    result = {
        "run_id": None,
        "source": "No recorded offline run available",
        "training": [],
        "updates": 0,
        "evaluation": [],
        "claim": "No training or improvement claim available",
        "model": model,
    }
    try:
        published = json.loads(
            (ROOT / "docs/experiments/measured-results.json").read_text(encoding="utf-8")
        )
        result.update(
            run_id="offline-dqn-100-40",
            source="Published measured experiment (historical)",
            training=[
                {"episode": i, "reward": reward, "loss": None}
                for i, reward in enumerate(published["training"]["episode_rewards"])
            ],
            updates=published["training"]["updates"],
            evaluation=published["evaluation"],
            claim=published["claim"],
        )
    except (OSError, ValueError, KeyError, TypeError):
        pass
    try:
        local = json.loads(
            (ROOT / "artifacts/experiment/experiment.json").read_text(encoding="utf-8")
        )
        training = [
            {"episode": row["episode"], "reward": row["reward"], "loss": row.get("loss")}
            for row in local["training"]
        ]
        result.update(
            run_id=f"offline-dqn-{local['train_seed']}-{len(training)}",
            source="Local offline experiment report",
            training=training,
            updates=local["updates"],
            claim=local["claim"],
        )
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return result
