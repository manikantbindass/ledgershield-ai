import pytest
from ledgershield.network import Network, NetworkConfig
from ledgershield.core import Rejected


def test_seeded_consensus_with_one_failure():
    histories = []
    for _ in range(2):
        net = Network()
        net.nodes["node_0"].behavior = "unavailable"
        net.demo_transaction()
        assert net.round()
        assert net.quorum == 3 and net.view > 0
        assert net.ledger.verify_chain()
        histories.append((net.summary(), net.ledger.chain[-1].hash, net.certificates))
    assert histories[0] == histories[1]


def test_signed_votes_reject_malicious_and_foreign_certificates():
    net = Network()
    net.nodes["node_1"].behavior = "malicious"
    assert net.round()
    cert = net.certificates[-1]
    b = net.ledger.chain[-1]
    assert net.verify_certificate(b, cert["commit"], "commit", cert["view"])
    assert not net.verify_certificate(b, cert["commit"], "prepare", cert["view"])
    assert not net.verify_certificate(b, cert["commit"], "commit", cert["view"] + 1)
    assert not net.verify_certificate(b, {"node_1": "00", "outsider": "00"}, "commit", 0)


def test_partition_stalls_without_lowering_quorum_and_recovers():
    net = Network()
    net.partition([["node_0", "node_1", "node_4"], ["node_2", "node_3", "node_5"]])
    assert not net.round()
    assert net.metrics["stalls"] == 1 and net.quorum == 3
    net.partitions.clear()
    assert net.round()


@pytest.mark.parametrize("config", [NetworkConfig(loss=1), NetworkConfig(latency_ms=300), NetworkConfig()])
def test_unreachable_and_timeout(config):
    net = Network(config)
    net.nodes["node_0"].behavior = "faulty"
    net.nodes["node_1"].behavior = "unavailable"
    assert not net.round()
    assert net.metrics["timeouts"] > 0
    assert net.quorum == 3


def test_snapshot_restore():
    net = Network()
    snapshot = net.snapshot()
    net.demo_transaction()
    net.round()
    net.restore(snapshot)
    assert net.tick == 0 and len(net.ledger.chain) == 1
    assert net.round()


def test_invalid_config():
    with pytest.raises(Rejected):
        NetworkConfig(validator_count=3)
