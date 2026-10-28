# Consensus assumptions

The implemented protocol is a centralized PBFT-style simulator over one canonical ledger, not formal distributed PBFT. Fixed N validators require `floor(2N/3)+1` valid signatures in each prepare/commit phase. N=4 requires 3. Membership and quorum do not shrink after failures, suspicious behavior or quarantine.

Votes bind chain ID, height, proposed hash, phase and view. Invalid signatures, outsiders and mismatched phases/views cannot count. Honest nodes vote for the validated proposal; faulty nodes abstain; unavailable nodes fail delivery; simulated malicious voters sign a wrong hash. Latency, jitter, independent loss, timeouts and partition links affect delivery. Bounded leader replacement increments views; missing quorum records a stall. Replica observer heights change only when commit propagation delivers.

Quorum intersection motivates a fault bound of floor((N-1)/3), but delivery and centralized scheduling assumptions matter. No independent per-replica locking, adversarial equivocation scheduler or certified distributed view change is implemented. Failed rounds do not produce finality. Block validity, signed-vote acceptance and atomic application execution are separate gates. Hash chaining alone does not prevent overspending; shared balances and nonces reject transaction conflicts.

Tests cover signed phase/view binding, supported single-failure progress, partitions/stalls without weakened quorum, recovery and repeatable transport. These establish behavior of this simulator, not resistance to unrestricted real-world attacks.
