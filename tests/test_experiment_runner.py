import json

import numpy as np
import pytest

from ledgershield.core import Rejected
from ledgershield.experiments import run_comparison, summarize
from ledgershield.learning import DQN


def trained(tmp_path):
    model = DQN(seed=9)
    state = np.ones(12, dtype=np.float32)
    for _ in range(35):
        model.learn((state, 0, 1.0, state, False))
    model.save(tmp_path / "dqn.json")
    (tmp_path / "experiment.json").write_text(
        json.dumps({"training": [{"seed": 100}], "updates": model.updates})
    )
    return tmp_path / "dqn.json"


def test_runner_matched_metrics_are_reproducible(tmp_path):
    checkpoint = trained(tmp_path)
    first = run_comparison(
        checkpoint,
        [21000],
        horizon=3,
        scenarios=["normal", "suspicious_voting"],
        output=tmp_path / "a",
    )
    second = run_comparison(
        checkpoint,
        [21000],
        horizon=3,
        scenarios=["normal", "suspicious_voting"],
        output=tmp_path / "b",
    )
    assert first == second and len(first["runs"]) == 6
    assert {r["policy"] for r in first["runs"]} == {"no_healing", "rule", "trained_dqn"}
    for row in first["runs"]:
        assert 0 <= row["network_availability"] <= 1
        assert 0 <= row["consensus_completion_rate"] <= 1
        assert row["throughput_tx_per_sim_second"] >= 0
        assert row["end_to_end_latency_ms"] is not None
    malicious = [r for r in first["runs"] if r["scenario"] == "suspicious_voting"]
    assert all(r["attack_tp"] == 1 and r["attack_detection_recall"] == 1 for r in malicious)
    assert (tmp_path / "a/runs.csv").exists()
    assert first["summary"]["rule"]["metrics"]["throughput_tx_per_sim_second"]["n"] == 2


def test_runner_rejects_untrained_and_leaked_evaluation(tmp_path):
    path = trained(tmp_path)
    with pytest.raises(Rejected, match="evaluation_seed_leakage"):
        run_comparison(path, [100], output=tmp_path / "invalid")
    DQN().save(path)
    with pytest.raises(Rejected, match="trained_checkpoint_required"):
        run_comparison(path, [21000], output=tmp_path / "invalid")


def test_summary_exposes_sample_count_and_exploratory_intervals():
    rows = [
        {
            "policy": policy,
            "seed": i,
            "scenario": "normal",
            "horizon": 1,
            "simulated_ticks": 1,
            "throughput": float(i),
            "tp": 0,
            "fp": 0,
            "fn": 0,
            "tn": 6,
            "attack_tp": 0,
            "attack_fp": 0,
            "attack_fn": 0,
        }
        for policy in ("no_healing", "rule", "trained_dqn")
        for i in range(6)
    ]
    result = summarize(rows)["rule"]
    assert result["runs"] == 6
    metric = result["metrics"]["throughput"]
    assert metric["n"] == 6 and metric["sample_variance"] > 0
    assert len(metric["exploratory_bootstrap_95_interval"]) == 2
    assert result["pooled_detection"]["recall"] is None
