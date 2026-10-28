"""Matched, labeled research experiments using the real detection/healing service."""

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np

from .core import Rejected
from .learning import DQN
from .network import NetworkConfig
from .recovery import ACTIONS
from .service import Service

SCENARIOS = {
    "normal": "honest",
    "node_failure": "unavailable",
    "suspicious_voting": "malicious",
    "faulty": "faulty",
}


class TrainedPolicy:
    def __init__(self, model, service):
        self.model, self.service = model, service

    def propose(self, alert, network):
        node = network.nodes[alert["node_id"]]
        stats, metrics = network.node_metrics[node.id], network.summary()
        observation = np.clip(
            np.array(
                [
                    metrics["availability"],
                    self.service.trust.get(node.id) / 100,
                    metrics["accepted"] / max(1, metrics["submitted"]),
                    float(network.last_round["committed"]),
                    metrics["message_latency_ms"] / network.config.timeout_ms,
                    stats["timeouts"] / max(1, stats["attempts"]),
                    stats["invalid_votes"] / max(1, stats["invalid_votes"] + stats["votes"]),
                    float(node.quarantined),
                    float(node.monitoring),
                    0,
                    0,
                    metrics["stalls"] / max(1, network.tick),
                ],
                dtype=np.float32,
            ),
            0,
            1,
        )
        return ACTIONS[self.model.act(observation)]


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def sample(policy, model, scenario, seed, horizon):
    svc = Service(
        NetworkConfig(seed=seed),
        mode="observe_only" if policy == "no_healing" else "autonomous_simulation",
    )
    if policy == "trained_dqn":
        svc.policy = TrainedPolicy(model, svc)
    target = "node_1"
    # Two honest warm-up rounds, identical across policies.
    for _ in range(2):
        svc.network.demo_transaction()
        svc.step()
    net = svc.network
    onset = net.tick
    net.nodes[target].behavior = SCENARIOS[scenario]
    first_alert = len(svc.detector.alerts)
    first_recovery = len(svc.recovery.audit)
    before = dict(net.metrics)
    processing_start = len(net.processing_latencies)
    availability = []
    for _ in range(horizon):
        net.demo_transaction()
        svc.step()
        availability.append(net.summary()["availability"])
    alerts = svc.detector.alerts[first_alert:]
    recovery = svc.recovery.audit[first_recovery:]
    positives = {target} if scenario != "normal" else set()
    predictions = {a["node_id"] for a in alerts}
    attacks = {target} if scenario == "suspicious_voting" else set()
    attack_predictions = {a["node_id"] for a in alerts if a["method"] == "invalid_signed_vote"}
    identities = set(net.nodes)
    tp, fp = len(predictions & positives), len(predictions - positives)
    fn, tn = len(positives - predictions), len(identities - positives - predictions)
    atp, afp, afn = (
        len(attacks & attack_predictions),
        len(attack_predictions - attacks),
        len(attacks - attack_predictions),
    )
    detections = [a["timestamp"] - onset for a in alerts if a["node_id"] in positives]
    successful = [r for r in recovery if r["status"] == "recovered" and r["node_id"] in positives]
    latency = net.processing_latencies[processing_start:]
    rounds = net.tick - onset
    return {
        "policy": policy,
        "scenario": scenario,
        "seed": seed,
        "horizon": horizon,
        "simulated_ticks": rounds,
        "throughput_tx_per_sim_second": (
            net.metrics["committed_transactions"] - before["committed_transactions"]
        )
        / max(1, rounds),
        "end_to_end_latency_ms": float(np.mean(latency)) if latency else None,
        "network_availability": float(np.mean(availability)),
        "consensus_completion_rate": (net.metrics["blocks"] - before["blocks"]) / max(1, rounds),
        "detection_precision": ratio(tp, tp + fp),
        "detection_recall": ratio(tp, tp + fn),
        "attack_detection_precision": ratio(atp, atp + afp),
        "attack_detection_recall": ratio(atp, atp + afn),
        "false_positive_rate": ratio(fp, fp + tn),
        "mean_time_to_detect_ticks": min(detections) if detections else None,
        "mean_time_to_recover_ticks": float(
            np.mean([r["after"]["simulated_seconds"] - onset for r in successful])
        )
        if successful
        else None,
        "unnecessary_interventions": sum(
            r["node_id"] not in positives
            and r["action"] != "observe"
            and r["status"] in ("recovered", "monitoring", "recommendation")
            for r in recovery
        ),
        "failed_recovery_attempts": sum(r["status"] == "rolled_back" for r in recovery),
        "recovery_attempts": sum("attempt" in r for r in recovery),
        "verified_recoveries": len(successful),
        "fault_detected": bool(detections),
        "fault_recovered": bool(successful),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "attack_tp": atp,
        "attack_fp": afp,
        "attack_fn": afn,
    }


def summarize(rows):
    output = {}
    excluded = {"policy", "scenario", "seed", "horizon", "simulated_ticks"}
    for policy in ("no_healing", "rule", "trained_dqn"):
        selected = [r for r in rows if r["policy"] == policy]
        metrics = {}
        for key in rows[0]:
            if key in excluded:
                continue
            values = np.array([r[key] for r in selected if r[key] is not None], dtype=float)
            interval = None
            if len(values) >= 5:
                rng = np.random.default_rng(901)
                means = values[rng.integers(0, len(values), (1000, len(values)))].mean(axis=1)
                interval = np.quantile(means, [0.025, 0.975]).tolist()
            metrics[key] = {
                "n": len(values),
                "mean": float(values.mean()) if len(values) else None,
                "sample_variance": float(values.var(ddof=1)) if len(values) > 1 else None,
                "exploratory_bootstrap_95_interval": interval,
            }
        totals = {
            key: sum(r[key] for r in selected)
            for key in ("tp", "fp", "fn", "tn", "attack_tp", "attack_fp", "attack_fn")
        }
        output[policy] = {
            "runs": len(selected),
            "metrics": metrics,
            "pooled_detection": {
                **totals,
                "precision": ratio(totals["tp"], totals["tp"] + totals["fp"]),
                "recall": ratio(totals["tp"], totals["tp"] + totals["fn"]),
                "false_positive_rate": ratio(totals["fp"], totals["fp"] + totals["tn"]),
                "attack_precision": ratio(
                    totals["attack_tp"], totals["attack_tp"] + totals["attack_fp"]
                ),
                "attack_recall": ratio(
                    totals["attack_tp"], totals["attack_tp"] + totals["attack_fn"]
                ),
            },
        }
    return output


def run_comparison(
    checkpoint, seeds=(20000, 20001, 20002), horizon=8, scenarios=None, output="artifacts/benchmark"
):
    path = Path(checkpoint)
    model = DQN.load(path)  # No silent untrained or rule fallback in this runner.
    if model.updates <= 0:
        raise Rejected("trained_checkpoint_required")
    selected = list(SCENARIOS) if scenarios is None else list(scenarios)
    if not seeds or len(set(seeds)) != len(seeds) or not 1 <= horizon <= 100:
        raise Rejected("invalid_experiment_config")
    if not selected or any(s not in SCENARIOS for s in selected):
        raise Rejected("invalid_scenario")
    manifest = json.loads(path.with_name("experiment.json").read_text())
    if manifest.get("updates") != model.updates or not manifest.get("training"):
        raise Rejected("checkpoint_training_manifest_mismatch")
    training_seeds = {row["seed"] for row in manifest["training"]}
    if training_seeds & set(seeds):
        raise Rejected("evaluation_seed_leakage")
    rows = [
        sample(policy, model, scenario, seed, horizon)
        for seed in seeds
        for scenario in selected
        for policy in ("no_healing", "rule", "trained_dqn")
    ]
    report = {
        "schema_version": 1,
        "configuration": {
            "implementation_sha256": hashlib.sha256(
                b"".join(
                    (Path(__file__).parent / name).read_bytes()
                    for name in (
                        "core.py",
                        "network.py",
                        "service.py",
                        "recovery.py",
                        "evidence.py",
                        "learning.py",
                        "experiments.py",
                    )
                )
            ).hexdigest(),
            "seeds": list(seeds),
            "horizon": horizon,
            "scenarios": selected,
            "node_count": 6,
            "validator_count": 4,
            "training_seed_count": len(training_seeds),
            "checkpoint_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "checkpoint_updates": model.updates,
        },
        "runs": rows,
        "summary": summarize(rows),
        "limitations": [
            "Centralized educational simulator; no real-world attack benchmark or hardware latency claim.",
            "DQN is trained in HealingEnv; alert-driven application evaluation is a distinct distribution. No retraining or automatic deployment occurs.",
            "Timing uses simulator ticks; recovery means the guarded action led to a new commit, not proof of restored Byzantine safety.",
            "Detection confusion counts are per-node per-episode fault indicators. Attack metrics use verified wrong-hash vote indicators and injected malicious-voting labels only.",
            "Null means undefined or unobserved; MTTD/MTTR condition on detected/recovered faults and exclude censored failures. Inspect fault_detected/fault_recovered and counts.",
            "Availability is averaged after application steps; completion includes recovery verification rounds. Unnecessary actions target known-unaffected identities.",
            "Bootstrap intervals are exploratory across this sampled seed/scenario mixture, not general security guarantees.",
        ],
    }
    folder = Path(output)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    with (folder / "runs.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", default="artifacts/experiment/dqn.json")
    parser.add_argument("--seeds", type=int, nargs="+", default=[20000, 20001, 20002])
    parser.add_argument("--horizon", type=int, default=8)
    parser.add_argument("--output", default="artifacts/benchmark")
    args = parser.parse_args()
    result = run_comparison(args.checkpoint, args.seeds, args.horizon, output=args.output)
    print(
        json.dumps(
            {
                "runs": len(result["runs"]),
                "output": args.output,
                "claim": "Measured results only; no RL superiority asserted",
            }
        )
    )
