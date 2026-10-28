"""Canonical Ed25519 transfers, atomic account execution, and hash-linked blocks."""

import hashlib
import json
from copy import deepcopy
from dataclasses import asdict, dataclass, field

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat


class Rejected(ValueError):
    def __init__(self, code, detail=""):
        self.code = code
        super().__init__(f"{code}: {detail}")


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def public_key(key):
    return key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()


def demo_key(seed, name):
    """Reproducible public simulator identities; NEVER use as real wallet keys."""
    return Ed25519PrivateKey.from_private_bytes(hashlib.sha256(f"{seed}:{name}".encode()).digest())


@dataclass(frozen=True)
class Transaction:
    sender: str
    receiver: str
    amount: int
    nonce: int
    chain_id: str = "ledgershield-local"
    signature: str = ""

    def payload(self):
        return {k: v for k, v in asdict(self).items() if k != "signature"}

    @property
    def tx_hash(self):
        return digest(self.to_dict())

    def to_dict(self):
        return asdict(self)

    @classmethod
    def signed(cls, key, receiver, amount, nonce, chain_id="ledgershield-local"):
        tx = cls(public_key(key), receiver, amount, nonce, chain_id)
        return cls(**tx.payload(), signature=key.sign(canonical(tx.payload())).hex())

    def validate(self, chain_id):
        if self.chain_id != chain_id:
            raise Rejected("wrong_chain")
        if type(self.amount) is not int or self.amount <= 0:
            raise Rejected("invalid_amount", "positive integer units required")
        if type(self.nonce) is not int or self.nonce < 0:
            raise Rejected("invalid_nonce")
        if self.sender == self.receiver:
            raise Rejected("self_transfer")
        try:
            if len(bytes.fromhex(self.receiver)) != 32 or len(bytes.fromhex(self.sender)) != 32:
                raise ValueError("invalid identity")
            if (
                self.receiver != bytes.fromhex(self.receiver).hex()
                or self.sender != bytes.fromhex(self.sender).hex()
                or len(self.signature) != 128
                or self.signature != bytes.fromhex(self.signature).hex()
            ):
                raise ValueError("noncanonical identity or signature")
            Ed25519PublicKey.from_public_bytes(bytes.fromhex(self.sender)).verify(
                bytes.fromhex(self.signature), canonical(self.payload())
            )
        except (ValueError, TypeError, InvalidSignature) as exc:
            raise Rejected("invalid_signature_or_identity") from exc


def merkle_root(transactions):
    """Tx-ID leaves; concatenate raw hashes; duplicate odd leaves; SHA-256 parents."""
    level = [bytes.fromhex(tx.tx_hash) for tx in transactions]
    if not level:
        return hashlib.sha256(b"").hexdigest()
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [hashlib.sha256(level[i] + level[i + 1]).digest() for i in range(0, len(level), 2)]
    return level[0].hex()


@dataclass(frozen=True)
class Block:
    index: int
    previous_hash: str
    transactions: tuple[Transaction, ...]
    validator: str
    timestamp: int
    chain_id: str = "ledgershield-local"
    genesis_hash: str = ""
    hash: str = field(default="")

    def __post_init__(self):
        object.__setattr__(self, "transactions", tuple(self.transactions))
        if not self.hash:
            object.__setattr__(self, "hash", self.compute_hash())

    def payload(self):
        return {
            "index": self.index,
            "previous_hash": self.previous_hash,
            "transactions": [tx.to_dict() for tx in self.transactions],
            "merkle_root": merkle_root(self.transactions),
            "validator": self.validator,
            "timestamp": self.timestamp,
            "chain_id": self.chain_id,
            "genesis_hash": self.genesis_hash,
        }

    def compute_hash(self):
        return digest(self.payload())

    def to_dict(self):
        return {**self.payload(), "hash": self.hash}


class LedgerState:
    def __init__(self, allocations=None, chain_id="ledgershield-local", genesis_timestamp=0):
        if (
            not isinstance(chain_id, str)
            or not 1 <= len(chain_id) <= 100
            or type(genesis_timestamp) is not int
            or genesis_timestamp < 0
        ):
            raise Rejected("invalid_genesis")
        self.allocations = dict(allocations or {})
        for address, balance in self.allocations.items():
            try:
                valid_address = (
                    len(bytes.fromhex(address)) == 32 and address == bytes.fromhex(address).hex()
                )
            except (ValueError, TypeError):
                valid_address = False
            if not valid_address or type(balance) is not int or balance < 0:
                raise Rejected("invalid_genesis")
        self.chain_id = chain_id
        self.accounts = dict(self.allocations)
        self.nonces = {}
        self.seen = set()
        self.pending_transactions = []
        config_hash = digest(
            {"chain_id": chain_id, "allocations": self.allocations, "timestamp": genesis_timestamp}
        )
        self.chain = [Block(0, "0" * 64, (), "genesis", genesis_timestamp, chain_id, config_hash)]

    def execute(self, transactions, accounts=None, nonces=None, seen=None):
        balances = dict(self.accounts if accounts is None else accounts)
        counters = dict(self.nonces if nonces is None else nonces)
        ids = set(self.seen if seen is None else seen)
        for tx in transactions:
            tx.validate(self.chain_id)
            if tx.tx_hash in ids:
                raise Rejected("duplicate_transaction")
            if tx.nonce != counters.get(tx.sender, 0):
                raise Rejected("nonce_conflict")
            if balances.get(tx.sender, 0) < tx.amount:
                raise Rejected("insufficient_funds")
            balances[tx.sender] -= tx.amount
            balances[tx.receiver] = balances.get(tx.receiver, 0) + tx.amount
            counters[tx.sender] = tx.nonce + 1
            ids.add(tx.tx_hash)
        return balances, counters, ids

    def submit(self, tx):
        self.execute([*self.pending_transactions, tx])
        self.pending_transactions.append(tx)

    def validate_block(self, block):
        last = self.chain[-1]
        if type(block.index) is not int or block.index < 1:
            raise Rejected("invalid_block_index")
        if not isinstance(block.validator, str) or not block.validator:
            raise Rejected("invalid_validator_identity")
        if block.hash != block.compute_hash():
            raise Rejected("tampered_block")
        if block.chain_id != self.chain_id or block.genesis_hash != self.chain[0].genesis_hash:
            raise Rejected("wrong_chain")
        if block.previous_hash != last.hash or block.index != last.index + 1:
            raise Rejected("invalid_linkage")
        if type(block.timestamp) is not int or block.timestamp < last.timestamp:
            raise Rejected("invalid_timestamp")
        return self.execute(block.transactions)

    def add_block(self, block):
        """Execution gate; consensus acceptance is checked separately by the simulator."""
        accounts, nonces, seen = self.validate_block(block)
        self.chain.append(deepcopy(block))
        self.accounts, self.nonces, self.seen = accounts, nonces, seen
        pending = [t for t in self.pending_transactions if t.tx_hash not in seen]
        self.pending_transactions = []
        for tx in pending:
            try:
                self.submit(tx)
            except Rejected:
                pass
        return True

    def verify_chain(self):
        replay = LedgerState(self.allocations, self.chain_id, self.chain[0].timestamp)
        if replay.chain[0] != self.chain[0]:
            raise Rejected("invalid_genesis")
        for block in self.chain[1:]:
            replay.add_block(block)
        if (replay.accounts, replay.nonces, replay.seen) != (self.accounts, self.nonces, self.seen):
            raise Rejected("state_mismatch")
        return True

    def get_balance(self, address):
        return self.accounts.get(address, 0)
