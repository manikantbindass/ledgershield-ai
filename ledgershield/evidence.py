"""Reproducible synthetic features, indicator alerts, and explainable trust changes."""

from dataclasses import asdict, dataclass

import numpy as np
from sklearn.ensemble import IsolationForest

from .core import Rejected, digest


def dataset(seed=101, size=500):
    rng = np.random.default_rng(seed)
    labels = np.zeros(size, dtype=int)
    labels[size * 4 // 5 :] = 1
    normal = np.column_stack(
        (rng.beta(1, 30, size), rng.beta(1, 20, size), np.clip(rng.normal(0.1, 0.025, size), 0, 1))
    )
    normal[labels == 1, :2] = rng.uniform(0.4, 1, (sum(labels), 2))
    return normal, labels


@dataclass
class DetectionConfig:
    invalid_vote_rate: float = 0.2
    timeout_rate: float = 0.6
    contamination: float = 0.05
    suppression_ticks: int = 5


class Detector:
    def __init__(self, config=None, seed=101):
        self.config = config or DetectionConfig()
        x, y = dataset(seed)
        self.model = IsolationForest(contamination=self.config.contamination, random_state=seed)
        self.model.fit(x[y == 0])
        self.alerts = []
        self.last = {}
        self.fingerprints = {}

    @staticmethod
    def features(stats, timeout_ms):
        values = np.array(
            [
                stats["invalid_votes"] / max(1, stats["invalid_votes"] + stats["votes"]),
                stats["timeouts"] / max(1, stats["attempts"]),
                stats["latency_ms"] / max(1, timeout_ms),
            ],
            dtype=float,
        )
        if not np.isfinite(values).all() or (values < 0).any():
            raise Rejected("invalid_features")
        return np.clip(values, 0, 1)

    def scan(self, node_id, stats, tick, timeout_ms):
        features = self.features(stats, timeout_ms)
        methods = []
        if features[0] >= self.config.invalid_vote_rate:
            methods.append(("invalid_signed_vote", "high", 0.99, True))
        if features[1] >= self.config.timeout_rate:
            methods.append(("repeated_timeout", "medium", 0.65, False))
        score = float(self.model.decision_function([features])[0])
        if score < 0:
            methods.append(("isolation_forest", "medium", min(0.9, 0.5 + abs(score)), False))
        created = []
        for method, severity, confidence, verified in methods:
            key = (node_id, method)
            fingerprint = (
                stats["invalid_votes"]
                if method == "invalid_signed_vote"
                else stats["timeouts"]
                if method == "repeated_timeout"
                else tuple(np.round(features, 4))
            )
            if self.fingerprints.get(key) == fingerprint:
                continue
            if tick - self.last.get(key, -1000) < self.config.suppression_ticks:
                continue
            alert = {
                "id": digest([node_id, method, tick]),
                "node_id": node_id,
                "timestamp": tick,
                "method": method,
                "severity": severity,
                "confidence": confidence,
                "verified": verified,
                "features": features.tolist(),
                "anomaly_score": score,
                "evidence": dict(stats),
                "explanation": "Indicator requiring context; an anomaly alone does not establish malicious intent.",
            }
            self.alerts.append(alert)
            created.append(alert)
            self.last[key] = tick
            self.fingerprints[key] = fingerprint
        return created


@dataclass
class TrustConfig:
    initial: float = 80
    minimum: float = 0
    maximum: float = 100
    threshold: float = 40
    decay: float = 0.01
    violation_weight: float = 15
    availability_weight: float = 1
    detector_weight: float = 0.5
    participation_reward: float = 0.2
    recovery_reward: float = 1

    def __post_init__(self):
        if (
            not self.minimum <= self.threshold <= self.initial <= self.maximum
            or not 0 <= self.decay <= 1
        ):
            raise Rejected("invalid_trust_config")
        if (
            min(
                self.violation_weight,
                self.availability_weight,
                self.detector_weight,
                self.participation_reward,
                self.recovery_reward,
            )
            < 0
        ):
            raise Rejected("invalid_trust_weights")


class TrustEngine:
    def __init__(self, config=None):
        self.config = config or TrustConfig()
        self.scores, self.updated, self.seen = {}, {}, set()
        self.audit = []

    def get(self, node):
        return self.scores.get(node, self.config.initial)

    def update(
        self, node, evidence_id, kind, tick, confidence=1, verified=False, provenance="simulator"
    ):
        key = (node, evidence_id)
        if key in self.seen:
            return self.get(node)
        if not 0 <= confidence <= 1:
            raise Rejected("invalid_confidence")
        cfg = self.config
        weights = {
            "invalid_signed_vote": -cfg.violation_weight if verified else -cfg.detector_weight,
            "repeated_timeout": -cfg.availability_weight,
            "isolation_forest": -cfg.detector_weight,
            "participation": cfg.participation_reward,
            "recovery": cfg.recovery_reward,
        }
        weights["valid_transaction"] = cfg.participation_reward
        weights["invalid_transaction"] = -cfg.violation_weight if verified else -cfg.detector_weight
        if kind not in weights:
            raise Rejected("unknown_evidence")
        before = self.get(node)
        elapsed = max(0, tick - self.updated.get(node, tick))
        decayed = cfg.initial + (before - cfg.initial) * (1 - cfg.decay) ** elapsed
        after = max(cfg.minimum, min(cfg.maximum, decayed + weights[kind] * confidence))
        self.scores[node], self.updated[node] = after, tick
        self.seen.add(key)
        self.audit.append(
            {
                "node_id": node,
                "evidence_id": evidence_id,
                "kind": kind,
                "timestamp": tick,
                "before": before,
                "decayed": decayed,
                "after": after,
                "delta": after - before,
                "confidence": confidence,
                "verified": verified,
                "provenance": provenance,
            }
        )
        return after

    def config_dict(self):
        return asdict(self.config)
