from collections import deque
from dataclasses import asdict
from time import time_ns
from uuid import uuid4

from .evidence import Detector, TrustEngine
from .network import Network
from .recovery import Orchestrator, RecoveryConfig
from .scenarios import ScenarioRuns


class Service:
    def __init__(self, config=None, mode="observe_only", policy=None):
        self.network = Network(config)
        self.detector = Detector()
        self.trust = TrustEngine()
        self.recovery = Orchestrator(self.network, self.trust, RecoveryConfig(mode=mode))
        self.policy = policy
        self.processed = {}
        self.running = False
        self.scenarios = []
        self.instance_id = str(uuid4())
        self.instance_started_at_ns = str(time_ns())
        self.history = deque(maxlen=240)
        self.events = deque(maxlen=500)
        self.event_counter = 0
        self.scenario_runs = ScenarioRuns(self)
        self.event(
            "service_ready",
            "Paused local simulator initialized",
            {"seed": self.network.config.seed},
        )

    def event(self, kind, summary, details=None):
        self.event_counter += 1
        self.events.append(
            {
                "id": f"{self.instance_id}:{self.event_counter}",
                "timestamp": self.network.tick,
                "kind": kind,
                "summary": summary,
                "details": details or {},
            }
        )

    def step(self):
        net = self.network
        net.round()
        # Collect first; recovery may advance the network clock.
        alerts = []
        tick = net.tick
        for name, stats in net.node_metrics.items():
            alerts.extend(self.detector.scan(name, stats, tick, net.config.timeout_ms))
            for metric, kind in (
                ("votes", "participation"),
                ("valid_transactions", "valid_transaction"),
                ("invalid_transactions", "invalid_transaction"),
            ):
                previous = self.processed.get((name, metric), 0)
                for counter in range(previous + 1, stats[metric] + 1):
                    self.trust.update(name, f"{metric}:{counter}", kind, tick, verified=True)
                self.processed[name, metric] = stats[metric]
        for alert in alerts:
            self.trust.update(
                alert["node_id"],
                alert["id"],
                alert["method"],
                tick,
                alert["confidence"],
                alert["verified"],
                alert["method"],
            )
            self.recovery.handle(alert, self.policy)
            self.event(
                "alert", alert["method"], {"alert_id": alert["id"], "node_id": alert["node_id"]}
            )
        self.scenario_runs.expire()
        self.recovery.expire_pending()
        self.history.append(self.state_metrics())
        self.event(
            "consensus",
            "Block committed" if net.last_round["committed"] else "Consensus stalled",
            {"height": len(net.ledger.chain) - 1, "view": net.view},
        )

    def state_metrics(self):
        records = self.recovery.audit
        return {
            **self.network.summary(),
            "anomalies": len(self.detector.alerts),
            "trust_changes": len(self.trust.audit),
            "recovery_attempts": sum("attempt" in r for r in records),
            "recovery_successes": sum(r["status"] == "recovered" for r in records),
            "recovery_failures": sum(r["status"] == "rolled_back" for r in records),
        }

    def state(self):
        net = self.network
        metrics = net.summary()
        recoveries = self.recovery.audit
        return {
            "project": "LedgerShield",
            "scope": "local research simulator",
            "instance_id": self.instance_id,
            "instance_started_at_ns": self.instance_started_at_ns,
            "revision": self.event_counter,
            "history": list(self.history),
            "partitioned_links": [list(p) for p in sorted(net.partitions)],
            "active_scenario": self.scenario_runs.active,
            "recent_events": list(self.events)[-30:],
            "running": self.running,
            "mode": self.recovery.config.mode,
            "config": asdict(net.config),
            "metrics": {
                **metrics,
                "anomalies": len(self.detector.alerts),
                "trust_changes": len(self.trust.audit),
                "recovery_attempts": sum("attempt" in r for r in recoveries),
                "recovery_successes": sum(r["status"] == "recovered" for r in recoveries),
                "recovery_failures": sum(r["status"] == "rolled_back" for r in recoveries),
            },
            "nodes": [
                {
                    **asdict(node),
                    "trust_score": self.trust.get(name),
                    "status": "isolated" if node.quarantined else node.behavior,
                    "telemetry": net.node_metrics[name],
                }
                for name, node in net.nodes.items()
            ],
            "consensus_health": 100 * float(net.last_round["committed"]),
            "consensus": net.last_round,
            "alerts": self.detector.alerts[-50:],
            "recovery": recoveries[-50:],
            "trust_audit": self.trust.audit[-50:],
            "transactions": [t.to_dict() for t in net.ledger.pending_transactions],
            "blocks": [b.to_dict() for b in net.ledger.chain[-10:]],
        }
