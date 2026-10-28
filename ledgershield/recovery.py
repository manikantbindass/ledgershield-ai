"""Reversible simulator actions with hard guards and explicit operational modes."""

from dataclasses import dataclass

from .core import Rejected, digest

ACTIONS = ("observe", "monitor", "quarantine", "restore", "resync", "reassign", "view_change")


@dataclass
class RecoveryConfig:
    mode: str = "observe_only"
    cooldown: int = 3
    retry_limit: int = 2
    timeout_ticks: int = 3

    def __post_init__(self):
        if self.mode not in ("observe_only", "approval_required", "autonomous_simulation"):
            raise Rejected("invalid_recovery_mode")
        if min(self.cooldown, self.retry_limit, self.timeout_ticks) < 1:
            raise Rejected("invalid_recovery_limits")


class RulePolicy:
    def propose(self, alert, network):
        node = network.nodes[alert["node_id"]]
        if alert["verified"] and not node.quarantined:
            return "quarantine"
        if node.behavior == "unavailable" and alert["method"] == "repeated_timeout":
            return "restore"
        return "monitor"


class Orchestrator:
    def __init__(self, network, trust, config=None):
        self.network, self.trust = network, trust
        self.config = config or RecoveryConfig()
        self.audit = []
        self.records = {}
        self.last, self.retries = {}, {}

    def handle(self, alert, policy=None):
        policy = policy or RulePolicy()
        policy_error = None
        try:
            action = policy.propose(alert, self.network)
        except Exception as exc:
            action = "observe"
            policy_error = type(exc).__name__
        if action not in ACTIONS:
            action = "observe"
            policy_error = "invalid_policy_action"
        record = self.propose(alert["node_id"], action, alert, digest([alert["id"], action]))
        if policy_error:
            record["policy_error"] = policy_error
        return record

    def propose(self, node_id, action, evidence, key):
        if key in self.records:
            return self.records[key]
        if action not in ACTIONS or node_id not in self.network.nodes:
            raise Rejected("invalid_recovery_action")
        record = {
            "id": key,
            "node_id": node_id,
            "action": action,
            "timestamp": self.network.tick,
            "evidence": evidence,
            "trust": self.trust.get(node_id),
            "expected_impact": action,
            "before": self.network.summary(),
            "status": "proposed",
            "proposed_mode": self.config.mode,
            "approval_required": self.config.mode == "approval_required"
            and action not in ("observe", "monitor", "reassign"),
            "safety_checks": {
                "permitted_action": True,
                "scope": "local_simulator",
                "execution_guards": "not_yet_evaluated",
            },
        }
        self.audit.append(record)
        self.records[key] = record
        if self.config.mode == "observe_only":
            record["status"] = "observed"
        elif self.config.mode == "approval_required" and action not in (
            "observe",
            "monitor",
            "reassign",
        ):
            record["status"] = "pending_approval"
        else:
            self.execute(record)
        return record

    def approve(self, key):
        record = self.records.get(key)
        if not record or record["status"] != "pending_approval":
            raise Rejected("approval_not_pending")
        if self.network.tick - record["timestamp"] > self.config.timeout_ticks:
            record["status"] = "expired"
            return record
        if self.config.mode == "observe_only":
            record["status"] = "blocked_mode"
            return record
        self.execute(record)
        return record

    def expire_pending(self):
        for record in self.audit:
            if (
                record["status"] == "pending_approval"
                and self.network.tick - record["timestamp"] > self.config.timeout_ticks
            ):
                record["status"] = "expired"

    def execute(self, record):
        net, cfg = self.network, self.config
        name, action = record["node_id"], record["action"]
        if name not in net.nodes:
            record["status"] = "target_unavailable"
            return
        node = net.nodes[name]
        pair = (name, action)
        record["safety_checks"].update(
            execution_guards="evaluated",
            quorum_required=net.quorum,
            cooldown_elapsed=net.tick - self.last.get(pair, -1000) >= cfg.cooldown,
            retry_budget_available=self.retries.get(pair, 0) < cfg.retry_limit,
        )
        if net.tick - self.last.get(pair, -1000) < cfg.cooldown:
            record["status"] = "cooldown"
            return
        if self.retries.get(pair, 0) >= cfg.retry_limit:
            record["status"] = "retry_limit"
            return
        if action == "quarantine":
            record["safety_checks"]["verified_evidence"] = bool(record["evidence"].get("verified"))
            if not record["evidence"].get("verified"):
                record["status"] = "blocked_unverified"
                return
            available = sum(
                not n.quarantined and n.behavior != "unavailable" and n.id != name
                for n in net.nodes.values()
                if n.validator
            )
            record["safety_checks"]["remaining_available_validators"] = available
            record["safety_checks"]["quorum_preserved"] = (
                not node.validator or available >= net.quorum
            )
            if node.validator and available < net.quorum:
                record["status"] = "blocked_quorum"
                return
        before = net.snapshot()
        self.last[pair] = net.tick
        self.retries[pair] = self.retries.get(pair, 0) + 1
        record["attempt"] = self.retries[pair]
        record["collateral_nodes"] = []
        try:
            if action == "observe":
                record["status"] = "no_action"
                return
            if action == "monitor":
                node.monitoring = True
                record["status"] = "monitoring"
                return
            if action == "reassign":
                record["status"] = "recommendation"
                return
            if action == "quarantine":
                node.quarantined = True
            elif action == "restore":
                if node.behavior == "malicious":
                    raise Rejected("unsafe_restore", "protocol violations require scenario reset")
                node.quarantined = False
                node.behavior = "honest"
            elif action == "resync":
                if node.behavior == "unavailable" or node.quarantined:
                    raise Rejected("resync_unreachable")
                source = next(
                    (
                        peer
                        for peer in net.validators
                        if peer != name and net.reachable(peer, name) and net.deliver(peer, name)
                    ),
                    None,
                )
                if source is None:
                    raise Rejected("resync_unreachable")
                net.ledger.verify_chain()
                node.height = len(net.ledger.chain) - 1
            elif action == "view_change":
                net.request_view_change()
            # A successful flag mutation alone is not proof of recovery.
            recovered = False
            for _ in range(cfg.timeout_ticks):
                if net.round():
                    recovered = True
                    break
            if not recovered:
                raise Rejected("recovery_timeout")
            if action == "resync" and node.height != len(net.ledger.chain) - 1:
                raise Rejected("resync_incomplete")
            record["status"] = "recovered"
            record["after"] = net.summary()
            record["duration_ticks"] = net.tick - record["timestamp"]
            record["collateral_nodes"] = [
                n.id for n in net.nodes.values() if n.height < len(net.ledger.chain) - 1
            ]
            self.retries[pair] = 0
            self.trust.update(name, record["id"], "recovery", net.tick)
        except Exception as exc:
            record["attempt_metrics"] = net.summary()
            record["duration_ticks"] = net.tick - record["timestamp"]
            net.restore(before)
            record["status"] = "rolled_back"
            record["reason"] = exc.code if isinstance(exc, Rejected) else "recovery_failed"
            record["after"] = net.summary()
