"""Bounded, reversible fault configuration. Committed history is never rewound."""

from uuid import uuid4

from .core import Rejected, Transaction, demo_key, public_key
from .network import Node


class ScenarioRuns:
    def __init__(self, service):
        self.service = service
        self.runs = []
        self.active = None
        self.saved = None

    def start(self, payload):
        if self.active:
            raise Rejected("scenario_already_active")
        net = self.service.network
        kind, target = payload.kind, payload.node_id
        if target not in net.nodes:
            raise Rejected("unknown_node")
        if kind == "sybil_like" and len(net.nodes) > 97:
            raise Rejected("scenario_node_limit")
        self.saved = {
            "behaviors": {n: node.behavior for n, node in net.nodes.items()},
            "partitions": set(net.partitions),
            "latency_ms": net.config.latency_ms,
            "running": self.service.running,
            "peers": [],
        }
        record = {
            "id": str(uuid4()),
            "kind": kind,
            "node_id": target,
            "duration_rounds": payload.duration_rounds,
            "started_at": net.tick,
            "expires_at": net.tick + payload.duration_rounds,
            "ended_at": None,
            "status": "running",
            "details": {},
            "scope": "controlled_simulation",
        }
        if kind in ("node_failure", "suspicious_voting"):
            net.nodes[target].behavior = "unavailable" if kind == "node_failure" else "malicious"
        elif kind == "delay":
            net.config.latency_ms = payload.latency_ms
            record["details"] = {"latency_ms": payload.latency_ms}
        elif kind == "partition":
            groups = [list(net.validators[::2]), list(net.validators[1::2])]
            for node in net.nodes.values():
                if not node.validator:
                    groups[len(groups[0]) % 2].append(node.id)
            net.partition(groups)
            record["details"] = {"groups": groups}
        elif kind == "sybil_like":
            # Three extra identities remain non-voting; membership and quorum stay fixed.
            for i in range(3):
                name = f"peer_{record['id'][:8]}_{i}"
                key = demo_key(net.config.seed, name)
                net.keys[name] = key
                net.nodes[name] = Node(name, public_key(key), False, "malicious")
                net.node_metrics[name] = dict(
                    attempts=0,
                    timeouts=0,
                    votes=0,
                    invalid_votes=0,
                    latency_ms=0,
                    valid_transactions=0,
                    invalid_transactions=0,
                )
                self.saved["peers"].append(name)
            record["details"] = {
                "identities": self.saved["peers"].copy(),
                "assumption": "Correlated synthetic observer identities, not a real Sybil attack benchmark",
            }
        elif kind == "conflicting_transactions":
            first = net.demo_transaction()
            conflict = Transaction.signed(net.wallet, net.receiver, 2, first.nonce)
            try:
                net.submit(conflict)
                result = "accepted"
            except Rejected as exc:
                result = exc.code
            record["details"] = {
                "first_transaction": first.tx_hash,
                "conflicting_transaction": conflict.tx_hash,
                "result": result,
            }
        self.active = record
        self.runs.append(record)
        self.service.running = True
        self.service.event(
            "scenario_started", f"Started {kind}", {"run_id": record["id"], "node_id": target}
        )
        return record

    def expire(self):
        if self.active and self.service.network.tick >= self.active["expires_at"]:
            self.stop("completed")

    def stop(self, status="stopped"):
        if not self.active:
            raise Rejected("no_active_scenario")
        net, record, saved = self.service.network, self.active, self.saved
        for name, behavior in saved["behaviors"].items():
            net.nodes[name].behavior = behavior
        for name in saved["peers"]:
            net.nodes.pop(name, None)
            net.keys.pop(name, None)
            net.node_metrics.pop(name, None)
        net.partitions = saved["partitions"]
        net.config.latency_ms = saved["latency_ms"]
        self.service.running = saved["running"]
        record.update(status=status, ended_at=net.tick)
        self.active, self.saved = None, None
        self.service.event(
            "scenario_ended",
            f"Scenario {status}; fault configuration restored",
            {"run_id": record["id"]},
        )
        return record
