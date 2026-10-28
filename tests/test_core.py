from dataclasses import replace
import pytest
from ledgershield.core import Block, LedgerState, Rejected, Transaction, demo_key, public_key, merkle_root


@pytest.fixture
def setup():
    alice, bob = demo_key(1, "alice"), public_key(demo_key(1, "bob"))
    return alice, bob, LedgerState({public_key(alice): 100})


def block(ledger, txs):
    return Block(len(ledger.chain), ledger.chain[-1].hash, txs, "node_0", 1,
                 ledger.chain_id, ledger.chain[0].genesis_hash)


def test_valid_roundtrip_and_merkle(setup):
    alice, bob, ledger = setup
    tx = Transaction.signed(alice, bob, 20, 0)
    assert Transaction(**tx.to_dict()) == tx
    b = block(ledger, [tx])
    assert b.compute_hash() == block(ledger, [tx]).hash
    assert merkle_root([tx]) == tx.tx_hash
    ledger.add_block(b)
    assert ledger.get_balance(bob) == 20
    assert ledger.get_balance(public_key(alice)) == 80
    assert ledger.verify_chain()


@pytest.mark.parametrize("mutation,code", [
    ({"amount": -1}, "invalid_amount"), ({"amount": 1.5}, "invalid_amount"),
    ({"amount": True}, "invalid_amount"), ({"nonce": -1}, "invalid_nonce"),
    ({"signature": "00"}, "invalid_signature_or_identity"),
    ({"receiver": "invalid"}, "invalid_signature_or_identity"),
    ({"chain_id": "other"}, "wrong_chain"),
])
def test_invalid_transaction(setup, mutation, code):
    alice, bob, ledger = setup
    with pytest.raises(Rejected, match=code):
        ledger.submit(replace(Transaction.signed(alice, bob, 20, 0), **mutation))


def test_tamper_and_linkage(setup):
    alice, bob, ledger = setup
    b = block(ledger, [Transaction.signed(alice, bob, 20, 0)])
    with pytest.raises(Rejected, match="tampered_block"):
        ledger.add_block(replace(b, validator="attacker"))
    with pytest.raises(Rejected, match="invalid_linkage"):
        ledger.add_block(replace(b, previous_hash="0" * 64, hash=""))
    assert len(ledger.chain) == 1


def test_duplicate_replay_and_conflict(setup):
    alice, bob, ledger = setup
    tx = Transaction.signed(alice, bob, 60, 0)
    ledger.submit(tx)
    with pytest.raises(Rejected, match="duplicate_transaction"):
        ledger.submit(tx)
    with pytest.raises(Rejected, match="nonce_conflict"):
        ledger.submit(Transaction.signed(alice, bob, 30, 0))
    with pytest.raises(Rejected, match="insufficient_funds"):
        ledger.submit(Transaction.signed(alice, bob, 60, 1))
    ledger.add_block(block(ledger, [tx]))
    with pytest.raises(Rejected, match="duplicate_transaction"):
        ledger.submit(tx)


def test_atomic_execution(setup):
    alice, bob, ledger = setup
    txs = [Transaction.signed(alice, bob, 60, 0), Transaction.signed(alice, bob, 60, 1)]
    with pytest.raises(Rejected, match="insufficient_funds"):
        ledger.add_block(block(ledger, txs))
    assert ledger.accounts == ledger.allocations
    assert not ledger.nonces and not ledger.seen


def test_chain_and_genesis_tamper(setup):
    alice, bob, ledger = setup
    ledger.add_block(block(ledger, [Transaction.signed(alice, bob, 1, 0)]))
    ledger.accounts[bob] = 500
    with pytest.raises(Rejected, match="state_mismatch"):
        ledger.verify_chain()
    other = LedgerState({public_key(alice): 200})
    assert other.chain[0].hash != ledger.chain[0].hash
