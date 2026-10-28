import numpy as np
import pytest

from ledgershield.core import Rejected
from ledgershield.evidence import Detector, TrustConfig, TrustEngine, dataset
from ledgershield.network import Network
from ledgershield.recovery import Orchestrator, RecoveryConfig


def evidence(verified=True):
    return {"verified": verified, "id": "alert", "method": "invalid_signed_vote"}


def test_labeled_detector_and_suppression():
    detector = Detector()
    normal = dict(attempts=100, timeouts=0, votes=100, invalid_votes=0, latency_ms=20)
    bad = dict(attempts=100, timeouts=80, votes=5, invalid_votes=50, latency_ms=100)
    assert not any(a["verified"] for a in detector.scan("good", normal, 1, 200))
    alerts = detector.scan("bad", bad, 1, 200)
    assert any(a["verified"] and a["method"] == "invalid_signed_vote" for a in alerts)
    assert detector.scan("bad", bad, 2, 200) == []
    x, y = dataset(202)
    scores = detector.model.decision_function(x)
    assert scores[y == 1].mean() < scores[y == 0].mean()
    assert not np.array_equal(dataset(101)[0], x)


def test_trust_bounds_duplicates_decay_and_transient_failures():
    trust = TrustEngine(TrustConfig(decay=0))
    for i in range(30):
        trust.update("bad", str(i), "invalid_signed_vote", i, verified=True)
        trust.update("good", str(i), "recovery", i)
    assert trust.get("bad") == 0 and trust.get("good") == 100
    count = len(trust.audit)
    trust.update("good", "29", "recovery", 50)
    assert len(trust.audit) == count
    trust = TrustEngine()
    trust.update("node", "one", "isolation_forest", 1)
    assert trust.get("node") > 79
    trust.update("node", "two", "participation", 100)
    assert trust.get("node") > 79.5


def test_observe_approval_idempotence_and_quorum_guard():
    net, trust = Network(), TrustEngine()
    orch = Orchestrator(net, trust)
    rec = orch.propose("node_1", "quarantine", evidence(), "a")
    assert rec["status"] == "observed" and not net.nodes["node_1"].quarantined
    assert orch.propose("node_1", "quarantine", evidence(), "a") is rec
    orch.config.mode = "approval_required"
    rec = orch.propose("node_1", "quarantine", evidence(), "b")
    assert rec["status"] == "pending_approval"
    net.nodes["node_1"].behavior = "malicious"
    assert orch.approve("b")["status"] == "recovered"
    rec = orch.propose("node_2", "quarantine", evidence(), "c")
    assert orch.approve("c")["status"] == "blocked_quorum"


def test_unverified_recovery_cannot_quarantine_and_rollback():
    net = Network()
    orch = Orchestrator(net, TrustEngine(), RecoveryConfig(mode="autonomous_simulation"))
    assert (
        orch.propose("node_1", "quarantine", evidence(False), "a")["status"] == "blocked_unverified"
    )
    net.config.loss = 1
    net.nodes["node_1"].behavior = "unavailable"
    before = net.snapshot()
    rec = orch.propose("node_1", "restore", evidence(False), "b")
    assert rec["status"] == "rolled_back"
    assert net.nodes["node_1"].behavior == "unavailable" and net.tick == before["tick"]
    assert orch.propose("node_1", "restore", evidence(False), "c")["status"] == "cooldown"
    with pytest.raises(Rejected):
        orch.propose("node_1", "shell", evidence(), "d")
