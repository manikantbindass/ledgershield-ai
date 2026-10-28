from dataclasses import replace

import pytest

from ledgershield.core import Block, LedgerState, Rejected, Transaction, demo_key, public_key
from ledgershield.evidence import DetectionConfig, TrustConfig, TrustEngine
from ledgershield.network import Network, NetworkConfig
from ledgershield.recovery import Orchestrator, RecoveryConfig
from ledgershield.service import Service


def test_observe_only_blocks_previously_pending_approval():
    net = Network()
    orchestrator = Orchestrator(net, TrustEngine(), RecoveryConfig(mode="approval_required"))
    action = orchestrator.propose("node_1", "quarantine", {"verified": True}, "pending")
    orchestrator.config = RecoveryConfig(mode="observe_only")
    assert orchestrator.approve(action["id"])["status"] == "blocked_mode"
    assert not net.nodes["node_1"].quarantined and net.tick == 0


def test_pending_approvals_expire_without_needing_a_click():
    service = Service(mode="approval_required")
    action = service.recovery.propose("node_1", "restore", {"verified": False}, "expires")
    for _ in range(4):
        service.step()
    assert action["status"] == "expired"


def test_resync_cannot_cross_a_partition_even_when_consensus_is_healthy():
    net = Network()
    assert net.round()
    net.nodes["node_5"].height = 0
    net.partition([[name for name in net.nodes if name != "node_5"], ["node_5"]])
    recovery = Orchestrator(net, TrustEngine(), RecoveryConfig(mode="autonomous_simulation"))
    record = recovery.propose("node_5", "resync", {}, "unreachable-resync")
    assert record["status"] == "rolled_back" and record["reason"] == "resync_unreachable"
    assert net.nodes["node_5"].height == 0
    assert record["attempt_metrics"]["height"] == 1


def test_failed_recovery_keeps_attempt_metrics_after_rollback():
    net = Network(NetworkConfig(loss=1))
    recovery = Orchestrator(net, TrustEngine(), RecoveryConfig(mode="autonomous_simulation"))
    record = recovery.propose("node_1", "restore", {}, "failed")
    assert record["status"] == "rolled_back"
    assert record["attempt_metrics"]["stalls"] > record["after"]["stalls"]
    assert record["duration_ticks"] == 3 and net.tick == 0


def test_policy_failure_is_visible_and_falls_back_safely():
    class BrokenPolicy:
        def propose(self, alert, network):
            raise RuntimeError("do-not-return-secret-in-error")

    recovery = Orchestrator(Network(), TrustEngine())
    record = recovery.handle({"id": "alert", "node_id": "node_1"}, BrokenPolicy())
    assert record["policy_error"] == "RuntimeError" and record["action"] == "observe"
    assert "do-not-return-secret" not in str(record)


def test_consensus_counts_only_signature_verified_commit_votes():
    net = Network()
    net.nodes["node_1"].behavior = "malicious"
    assert net.round()
    assert net.last_round["votes"] == 3
    assert len(net.certificates[-1]["commit"]) == 4


def test_production_delay_includes_jitter_and_timeouts():
    net = Network(NetworkConfig(latency_ms=10, jitter_ms=20))
    assert net.round()
    # Four validators each receive/return messages in prepare and commit.
    assert net.last_round["delay_ms"] == sum(net.latencies[:16])
    net = Network(NetworkConfig(latency_ms=10, jitter_ms=0, timeout_ms=200))
    net.nodes["node_1"].behavior = "unavailable"
    assert net.round()
    assert net.last_round["delay_ms"] > 16 * 10


@pytest.mark.parametrize("timestamp", [-1, True, "0", float("nan")])
def test_genesis_rejects_invalid_timestamp(timestamp):
    with pytest.raises(Rejected, match="invalid_genesis"):
        LedgerState(genesis_timestamp=timestamp)


@pytest.mark.parametrize("chain_id", [None, "", [], "x" * 101])
def test_genesis_rejects_invalid_chain_id(chain_id):
    with pytest.raises(Rejected, match="invalid_genesis"):
        LedgerState(chain_id=chain_id)


def test_block_bool_index_cannot_masquerade_as_height_one():
    ledger = LedgerState()
    block = Block(
        True, ledger.chain[0].hash, (), "node_0", 1, ledger.chain_id, ledger.chain[0].genesis_hash
    )
    with pytest.raises(Rejected, match="invalid_block_index"):
        ledger.add_block(block)
    with pytest.raises(Rejected, match="invalid_validator_identity"):
        ledger.add_block(replace(block, index=1, validator="", hash=""))


@pytest.mark.parametrize("config", [dict(jitter_ms=0.5), dict(seed=True), dict(loss="bad")])
def test_malformed_network_config_has_consistent_rejection(config):
    with pytest.raises(Rejected):
        NetworkConfig(**config)


def test_nonfinite_trust_and_invalid_detector_configuration_rejected():
    with pytest.raises(Rejected):
        TrustConfig(violation_weight=float("nan"))
    with pytest.raises(Rejected):
        DetectionConfig(suppression_ticks=0)


def test_identity_and_signature_text_are_canonical():
    key = demo_key(42, "alice")
    target = public_key(demo_key(42, "bob"))
    tx = Transaction.signed(key, target, 1, 0)
    with pytest.raises(Rejected, match="invalid_signature_or_identity"):
        replace(tx, receiver=target.upper()).validate(tx.chain_id)
    with pytest.raises(Rejected, match="invalid_signature_or_identity"):
        replace(tx, signature=" ".join(tx.signature[i : i + 2] for i in range(0, 128, 2))).validate(
            tx.chain_id
        )
    with pytest.raises(Rejected, match="invalid_genesis"):
        LedgerState({target.upper(): 100})


def test_suspicious_voting_requires_an_actual_validator():
    from backend.models import ScenarioRunRequest

    service = Service()
    with pytest.raises(Rejected, match="scenario_requires_validator"):
        service.scenario_runs.start(ScenarioRunRequest(kind="suspicious_voting", node_id="node_5"))
    assert service.scenario_runs.active is None and not service.running


def test_sybil_identity_sequence_is_reproducible():
    from backend.models import ScenarioRunRequest

    runs = []
    for _ in range(2):
        service = Service()
        record = service.scenario_runs.start(ScenarioRunRequest(kind="sybil_like"))
        runs.append(
            {name: service.network.nodes[name].identity for name in record["details"]["identities"]}
        )
    assert runs[0] == runs[1]


def test_archive_tracks_full_collections_and_skips_unchanged_writes():
    from types import SimpleNamespace

    from backend.database import archive

    class Store:
        def put_many(self, rows):
            self.rows = list(rows)

    service, store = Service(), Store()
    app = SimpleNamespace(state=SimpleNamespace(store=store, service=service, experiments={}))
    service.network.demo_transaction()
    for _ in range(12):
        service.step()
    archive(app)
    assert sum(kind == "block" for kind, key, payload in store.rows) == 13
    assert sum(kind == "trust" for kind, key, payload in store.rows) > 50
    assert sum(kind == "transaction" for kind, key, payload in store.rows) == 1
    archive(app)
    assert store.rows == []


def test_failed_archive_is_not_cached_as_persisted():
    from types import SimpleNamespace

    from backend.database import archive

    class BrokenStore:
        def put_many(self, rows):
            assert list(rows)
            raise RuntimeError("storage unavailable")

    app = SimpleNamespace(
        state=SimpleNamespace(store=BrokenStore(), service=Service(), experiments={})
    )
    for _ in range(2):
        with pytest.raises(RuntimeError, match="storage unavailable"):
            archive(app)
        assert not getattr(app.state, "archive_cache", {})


def test_failed_websocket_handshake_does_not_leak_connection_slot():
    import asyncio
    from types import SimpleNamespace

    from backend.main import stream

    class FailedHandshake:
        headers = {}
        application_state = SimpleNamespace(name="CONNECTING")
        app = SimpleNamespace(state=SimpleNamespace(websocket_count=0))

        async def accept(self):
            raise RuntimeError("handshake interrupted")

        async def close(self, **kwargs):
            self.closed = kwargs

    ws = FailedHandshake()
    asyncio.run(stream(ws, True))
    assert ws.app.state.websocket_count == 0
    assert ws.closed["code"] == 1011


@pytest.mark.parametrize(
    "stats", [dict(attempts=-1), dict(attempts=1, timeouts=2), dict(votes=float("nan"))]
)
def test_malformed_detector_telemetry_is_rejected(stats):
    from ledgershield.evidence import Detector

    baseline = dict(invalid_votes=0, votes=0, timeouts=0, attempts=0, latency_ms=0)
    baseline.update(stats)
    with pytest.raises(Rejected, match="invalid_features"):
        Detector.features(baseline, 200)


def test_rl_lab_does_not_mix_local_training_with_another_runs_evaluation(tmp_path, monkeypatch):
    import json

    from backend import research

    (tmp_path / "artifacts" / "experiment").mkdir(parents=True)
    report = {
        "train_seed": 200,
        "updates": 5,
        "claim": "Measured local run",
        "training": [{"episode": 0, "reward": 4, "loss": 0.2}],
        "evaluation": [
            {
                "policy": "rule",
                "seed": 12000,
                "reward": 7,
                "committed_transactions": 3,
                "recoveries": 1,
            }
        ],
    }
    (tmp_path / "artifacts" / "experiment" / "experiment.json").write_text(json.dumps(report))
    monkeypatch.setattr(research, "ROOT", tmp_path)
    result = research.learning_report()
    assert result["run_id"] == "offline-dqn-200-1"
    assert result["evaluation"] == [
        {
            "policy": "rule",
            "episodes": 1,
            "seeds": [12000, 12000],
            "mean_reward": 7,
            "committed_transactions": 3,
            "recoveries": 1,
        }
    ]
