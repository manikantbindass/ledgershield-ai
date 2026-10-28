"""Seeded, centralized PBFT-style simulation, not a distributed PBFT implementation."""

import random
from copy import deepcopy
from dataclasses import dataclass

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .core import Block, LedgerState, Rejected, Transaction, canonical, demo_key, public_key


@dataclass
class Node:
    id: str
    identity: str
    validator: bool
    behavior: str = "honest"
    quarantined: bool = False
    monitoring: bool = False
    height: int = 0


@dataclass
class NetworkConfig:
    seed: int = 42
    node_count: int = 6
    validator_count: int = 4
    latency_ms: int = 20
    jitter_ms: int = 10
    loss: float = 0.0
    timeout_ms: int = 200
    max_views: int = 4

    def __post_init__(self):
        if any(
            type(value) is not int
            for value in (
                self.seed,
                self.node_count,
                self.validator_count,
                self.latency_ms,
                self.jitter_ms,
                self.timeout_ms,
                self.max_views,
            )
        ):
            raise Rejected("invalid_network_config")
        if not 4 <= self.validator_count <= self.node_count <= 100:
            raise Rejected("invalid_network_size", "4 <= validators <= nodes <= 100")
        if (
            type(self.loss) not in (int, float)
            or not 0 <= self.loss <= 1
            or min(self.latency_ms, self.jitter_ms) < 0
        ):
            raise Rejected("invalid_transport")
        if self.timeout_ms <= 0 or not 1 <= self.max_views <= 100:
            raise Rejected("invalid_timeout")


class Network:
    def __init__(self, config=None):
        self.config = config or NetworkConfig()
        self.rng = random.Random(self.config.seed)
        self.keys = {
            f"node_{i}": demo_key(self.config.seed, f"node_{i}")
            for i in range(self.config.node_count)
        }
        self.nodes = {
            name: Node(name, public_key(key), i < self.config.validator_count)
            for i, (name, key) in enumerate(self.keys.items())
        }
        self.validators = tuple(n.id for n in self.nodes.values() if n.validator)
        self.wallet = demo_key(self.config.seed, "alice")
        self.receiver = public_key(demo_key(self.config.seed, "bob"))
        self.ledger = LedgerState({public_key(self.wallet): 1_000_000})
        self.partitions = set()
        self.view = 0
        self.tick = 0
        self.metrics = {
            k: 0
            for k in (
                "submitted",
                "accepted",
                "rejected",
                "committed_transactions",
                "blocks",
                "messages",
                "delivered",
                "timeouts",
                "stalls",
                "view_changes",
                "invalid_votes",
                "failed_requests",
                "propagation_failures",
                "vote_opportunities",
                "transport_elapsed_ms",
            )
        }
        self.latencies = []
        self.processing_latencies = []
        self.block_delays = []
        self.propagation_delays = []
        self.pending_at = {}
        self.transaction_records = {}
        self.node_metrics = {
            name: {
                "attempts": 0,
                "timeouts": 0,
                "votes": 0,
                "invalid_votes": 0,
                "latency_ms": 0,
                "valid_transactions": 0,
                "invalid_transactions": 0,
            }
            for name in self.nodes
        }
        self.certificates = []
        self.last_round = {"committed": False, "votes": 0, "reason": "not_started"}

    @property
    def quorum(self):
        return (2 * len(self.validators)) // 3 + 1

    def submit(self, tx):
        self.metrics["submitted"] += 1
        authenticated = False
        try:
            tx.validate(self.ledger.chain_id)
            authenticated = True
            self.ledger.submit(tx)
        except Rejected as exc:
            self.metrics["rejected"] += 1
            self.transaction_records.setdefault(
                tx.tx_hash,
                {
                    "tx_hash": tx.tx_hash,
                    "transaction": tx.to_dict(),
                    "status": "rejected",
                    "submitted_at": self.tick,
                    "rejection_code": exc.code,
                },
            )
            # Never attribute forged signatures to the claimed sender.
            if authenticated:
                for node in self.nodes.values():
                    if node.identity == tx.sender:
                        self.node_metrics[node.id]["invalid_transactions"] += 1
            raise
        self.metrics["accepted"] += 1
        self.transaction_records[tx.tx_hash] = {
            "tx_hash": tx.tx_hash,
            "transaction": tx.to_dict(),
            "status": "pending",
            "submitted_at": self.tick,
        }
        for node in self.nodes.values():
            if node.identity == tx.sender:
                self.node_metrics[node.id]["valid_transactions"] += 1
        self.pending_at[tx.tx_hash] = self.tick

    def demo_transaction(self):
        sender = public_key(self.wallet)
        nonce = self.ledger.nonces.get(sender, 0) + sum(
            t.sender == sender for t in self.ledger.pending_transactions
        )
        tx = Transaction.signed(self.wallet, self.receiver, 1, nonce)
        self.submit(tx)
        return tx

    def reachable(self, src, dst):
        a, b = self.nodes[src], self.nodes[dst]
        return (
            not a.quarantined
            and not b.quarantined
            and a.behavior != "unavailable"
            and b.behavior != "unavailable"
            and tuple(sorted((src, dst))) not in self.partitions
        )

    def deliver(self, src, dst):
        self.metrics["messages"] += 1
        stats = self.node_metrics[dst]
        stats["attempts"] += 1
        delay = self.config.latency_ms + self.rng.randint(0, self.config.jitter_ms)
        if (
            not self.reachable(src, dst)
            or self.rng.random() < self.config.loss
            or delay > self.config.timeout_ms
        ):
            self.metrics["timeouts"] += 1
            self.metrics["transport_elapsed_ms"] += self.config.timeout_ms
            stats["timeouts"] += 1
            return False
        self.metrics["delivered"] += 1
        self.metrics["transport_elapsed_ms"] += delay
        stats["latency_ms"] = delay
        self.latencies.append(delay)
        return True

    def vote_payload(self, block, phase, view):
        return {
            "chain": self.ledger.chain_id,
            "height": block.index,
            "hash": block.hash,
            "phase": phase,
            "view": view,
        }

    def certificate_voters(self, block, votes, phase, view):
        valid = set()
        payload = canonical(self.vote_payload(block, phase, view))
        for name, signature in votes.items():
            if name not in self.validators:
                continue
            try:
                Ed25519PublicKey.from_public_bytes(bytes.fromhex(self.nodes[name].identity)).verify(
                    bytes.fromhex(signature), payload
                )
                valid.add(name)
            except (InvalidSignature, ValueError, TypeError):
                continue
        return valid

    def verify_certificate(self, block, votes, phase, view):
        return len(self.certificate_voters(block, votes, phase, view)) >= self.quorum

    def round(self):
        self.tick += 1
        self.ledger.verify_chain()
        start_transport = self.metrics["transport_elapsed_ms"]
        for _ in range(self.config.max_views):
            leader = self.validators[self.view % len(self.validators)]
            node = self.nodes[leader]
            if node.behavior != "honest" or node.quarantined:
                self.deliver(leader, leader)
                self.request_view_change()
                continue
            block = Block(
                len(self.ledger.chain),
                self.ledger.chain[-1].hash,
                tuple(self.ledger.pending_transactions),
                leader,
                self.tick,
                self.ledger.chain_id,
                self.ledger.chain[0].genesis_hash,
            )
            self.ledger.validate_block(block)
            prepare, commit = {}, {}
            for phase, votes in (("prepare", prepare), ("commit", commit)):
                if phase == "commit" and not self.verify_certificate(
                    block, prepare, "prepare", self.view
                ):
                    break
                for name in self.validators:
                    self.metrics["vote_opportunities"] += 1
                    participant = self.nodes[name]
                    if not self.deliver(leader, name) or not self.deliver(name, leader):
                        continue
                    if participant.behavior == "faulty":
                        continue
                    payload = self.vote_payload(block, phase, self.view)
                    if participant.behavior == "malicious":
                        payload["hash"] = "0" * 64
                        self.metrics["invalid_votes"] += 1
                        self.node_metrics[name]["invalid_votes"] += 1
                    else:
                        self.node_metrics[name]["votes"] += 1
                    votes[name] = self.keys[name].sign(canonical(payload)).hex()
            if self.verify_certificate(
                block, prepare, "prepare", self.view
            ) and self.verify_certificate(block, commit, "commit", self.view):
                self.ledger.add_block(block)
                self.certificates.append(
                    {"height": block.index, "view": self.view, "prepare": prepare, "commit": commit}
                )
                self.metrics["blocks"] += 1
                self.metrics["committed_transactions"] += len(block.transactions)
                for tx in block.transactions:
                    self.processing_latencies.append(
                        (self.tick - self.pending_at.pop(tx.tx_hash, self.tick)) * 1000
                    )
                    if tx.tx_hash in self.transaction_records:
                        self.transaction_records[tx.tx_hash].update(
                            status="committed", committed_at=self.tick
                        )
                delay = self.metrics["transport_elapsed_ms"] - start_transport
                self.block_delays.append(delay)
                for name in self.nodes:
                    if self.deliver(leader, name):
                        self.nodes[name].height = block.index
                        self.propagation_delays.append(self.node_metrics[name]["latency_ms"])
                    else:
                        self.metrics["propagation_failures"] += 1
                self.last_round = {
                    "committed": True,
                    "votes": len(self.certificate_voters(block, commit, "commit", self.view)),
                    "leader": leader,
                    "height": block.index,
                    "delay_ms": delay,
                }
                return True
            self.request_view_change()
        self.metrics["stalls"] += 1
        self.last_round = {"committed": False, "votes": 0, "reason": "quorum_unavailable"}
        return False

    def request_view_change(self):
        self.view += 1
        self.metrics["view_changes"] += 1

    def partition(self, groups):
        names = set().union(*(set(g) for g in groups))
        if names != set(self.nodes) or sum(map(len, groups)) != len(names):
            raise Rejected("invalid_partition")
        self.partitions = {
            tuple(sorted((a, b)))
            for i, group in enumerate(groups)
            for other in groups[i + 1 :]
            for a in group
            for b in other
        }

    def snapshot(self):
        return deepcopy({k: v for k, v in self.__dict__.items() if k not in ("keys", "wallet")})

    def restore(self, state):
        keys, wallet = self.keys, self.wallet
        self.__dict__ = deepcopy(state)
        self.keys, self.wallet = keys, wallet

    def summary(self):
        m = self.metrics
        return {
            **m,
            "simulated_seconds": self.tick,
            "throughput": m["committed_transactions"] / max(1, self.tick),
            "transaction_latency_ms": sum(self.processing_latencies)
            / max(1, len(self.processing_latencies)),
            "message_latency_ms": sum(self.latencies) / max(1, len(self.latencies)),
            "block_delay_ms": sum(self.block_delays) / max(1, len(self.block_delays)),
            "propagation_delay_ms": sum(self.propagation_delays)
            / max(1, len(self.propagation_delays)),
            "availability": sum(
                n.behavior != "unavailable" and not n.quarantined for n in self.nodes.values()
            )
            / len(self.nodes),
            "participation": sum(s["votes"] for s in self.node_metrics.values())
            / max(1, m["vote_opportunities"]),
            "voting_consistency": 1
            - m["invalid_votes"]
            / max(1, m["invalid_votes"] + sum(s["votes"] for s in self.node_metrics.values())),
            "height": len(self.ledger.chain) - 1,
            "quorum": self.quorum,
            "view": self.view,
        }
