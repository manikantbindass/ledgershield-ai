from dataclasses import asdict
from .evidence import Detector, TrustEngine
from .network import Network, NetworkConfig
from .recovery import Orchestrator, RecoveryConfig


class Service:
    def __init__(self, config=None, mode="observe_only"):
        self.network = Network(config)
        self.detector = Detector()
        self.trust = TrustEngine()
        self.recovery = Orchestrator(self.network, self.trust, RecoveryConfig(mode=mode))
        self.processed = {}
        self.running = False
        self.scenarios = []

    def step(self):
        net = self.network
        net.round()
        # Collect first; recovery may advance the network clock.
        alerts = []
        tick = net.tick
        for name, stats in net.node_metrics.items():
            alerts.extend(self.detector.scan(name, stats, tick, net.config.timeout_ms))
            for metric, kind in (("votes", "participation"),
                                 ("valid_transactions", "valid_transaction"),
                                 ("invalid_transactions", "invalid_transaction")):
                previous = self.processed.get((name, metric), 0)
                for counter in range(previous + 1, stats[metric] + 1):
                    self.trust.update(name, f"{metric}:{counter}", kind, tick, verified=True)
                self.processed[name, metric] = stats[metric]
        for alert in alerts:
            self.trust.update(alert["node_id"], alert["id"], alert["method"], tick,
                              alert["confidence"], alert["verified"], alert["method"])
            self.recovery.handle(alert)

    def state(self):
        net = self.network
        metrics = net.summary()
        recoveries = self.recovery.audit
        return {"project": "LedgerShield", "scope": "local research simulator",
                "running": self.running,
                "mode": self.recovery.config.mode, "config": asdict(net.config),
                "metrics": {**metrics, "anomalies": len(self.detector.alerts),
                            "trust_changes": len(self.trust.audit),
                            "recovery_attempts": sum("attempt" in r for r in recoveries),
                            "recovery_successes": sum(r["status"] == "recovered" for r in recoveries),
                            "recovery_failures": sum(r["status"] == "rolled_back" for r in recoveries)},
                "nodes": [{**asdict(node), "trust_score": self.trust.get(name),
                           "status": "isolated" if node.quarantined else node.behavior,
                           "telemetry": net.node_metrics[name]} for name, node in net.nodes.items()],
                "consensus_health": 100 * float(net.last_round["committed"]),
                "consensus": net.last_round, "alerts": self.detector.alerts[-50:],
                "recovery": recoveries[-50:], "trust_audit": self.trust.audit[-50:],
                "transactions": [t.to_dict() for t in net.ledger.pending_transactions],
                "blocks": [b.to_dict() for b in net.ledger.chain[-10:]]}
