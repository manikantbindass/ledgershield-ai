"""Versioned public API schemas. Private simulator keys are never modeled here."""

from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TxPayload(Input):
    model_config = ConfigDict(extra="forbid", strict=True)
    sender: str = Field(pattern=r"^[0-9a-f]{64}$")
    receiver: str = Field(pattern=r"^[0-9a-f]{64}$")
    amount: StrictInt = Field(gt=0)
    nonce: StrictInt = Field(ge=0)
    chain_id: str = Field(default="ledgershield-local", max_length=100)
    signature: str = Field(pattern=r"^[0-9a-f]{128}$")


class ErrorInfo(BaseModel):
    code: str
    detail: str
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorInfo


T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    offset: int
    limit: int
    storage: Literal["in_memory"] = "in_memory"


class Telemetry(BaseModel):
    attempts: int
    timeouts: int
    votes: int
    invalid_votes: int
    latency_ms: int
    valid_transactions: int
    invalid_transactions: int


class NodeResponse(BaseModel):
    id: str
    identity: str
    validator: bool
    behavior: Literal["honest", "faulty", "unavailable", "malicious"]
    quarantined: bool
    monitoring: bool
    height: int
    trust_score: float
    status: str
    telemetry: Telemetry


class BlockResponse(BaseModel):
    index: int
    previous_hash: str
    transactions: list[TxPayload]
    merkle_root: str
    validator: str
    timestamp: int
    chain_id: str
    genesis_hash: str
    hash: str


class TransactionResponse(BaseModel):
    tx_hash: str
    transaction: TxPayload
    status: Literal["pending", "committed", "rejected"]
    submitted_at: int
    committed_at: int | None = None
    rejection_code: str | None = None


class AlertResponse(BaseModel):
    id: str
    node_id: str
    timestamp: int
    method: str
    severity: str
    confidence: float
    verified: bool
    features: list[float]
    anomaly_score: float
    evidence: Telemetry
    explanation: str


class TrustResponse(BaseModel):
    node_id: str
    score: float
    initial: float
    minimum: float
    maximum: float
    threshold: float
    updated_at: int | None
    evidence_count: int


class MetricsResponse(BaseModel):
    vote_opportunities: int = 0
    submitted: int
    accepted: int
    rejected: int
    committed_transactions: int
    blocks: int
    messages: int
    delivered: int
    timeouts: int
    stalls: int
    view_changes: int
    invalid_votes: int
    failed_requests: int
    propagation_failures: int
    simulated_seconds: int
    throughput: float
    transaction_latency_ms: float
    message_latency_ms: float
    block_delay_ms: float
    propagation_delay_ms: float
    availability: float
    participation: float
    voting_consistency: float
    height: int
    quorum: int
    view: int
    anomalies: int = 0
    trust_changes: int = 0
    recovery_attempts: int = 0
    recovery_successes: int = 0
    recovery_failures: int = 0


class ConsensusResponse(BaseModel):
    committed: bool
    votes: int
    reason: str | None = None
    leader: str | None = None
    height: int | None = None
    delay_ms: int | None = None


class NetworkSettings(BaseModel):
    seed: int
    node_count: int
    validator_count: int
    latency_ms: int
    jitter_ms: int
    loss: float
    timeout_ms: int
    max_views: int


class OverviewResponse(BaseModel):
    project: Literal["LedgerShield"] = "LedgerShield"
    storage: Literal["in_memory"] = "in_memory"
    running: bool
    mode: str
    config: NetworkSettings
    metrics: MetricsResponse
    consensus: ConsensusResponse


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    integrity: bool
    running: bool
    version: Literal["v1"] = "v1"
    storage: Literal["in_memory"] = "in_memory"


class HealingResponse(BaseModel):
    id: str
    node_id: str
    action: str
    timestamp: int
    evidence: dict
    trust: float
    expected_impact: str
    before: dict[str, int | float]
    status: str
    after: dict[str, int | float] | None = None
    attempt: int | None = None
    collateral_nodes: list[str] = Field(default_factory=list)
    duration_ticks: int | None = None
    reason: str | None = None
    safety_checks: dict = Field(default_factory=dict)
    approval_required: bool = False
    proposed_mode: str = "observe_only"


class Scenario(Input):
    node_id: str = Field(min_length=1, max_length=64)
    behavior: Literal["honest", "faulty", "unavailable", "malicious"]


class ScenarioResponse(Scenario):
    id: str
    timestamp: int
    applied: bool = True


class Mode(Input):
    mode: Literal["observe_only", "approval_required", "autonomous_simulation"]


class Reset(Input):
    seed: int = 42
    node_count: int = Field(default=6, ge=4, le=100)
    validator_count: int = Field(default=4, ge=4, le=100)
    loss: float = Field(default=0, ge=0, le=1, allow_inf_nan=False)
    latency_ms: int = Field(default=20, ge=0, le=10000)
    timeout_ms: int = Field(default=200, gt=0, le=10000)

    @model_validator(mode="after")
    def valid_membership(self) -> "Reset":
        if self.validator_count > self.node_count:
            raise ValueError("validator_count must not exceed node_count")
        return self


class Partition(Input):
    groups: list[list[str]] = Field(max_length=100)


class PartitionResponse(BaseModel):
    partitioned_links: int


class AcceptedResponse(BaseModel):
    status: Literal["accepted_to_mempool"] = "accepted_to_mempool"
    tx_hash: str


class EvaluationRequest(Input):
    policy: Literal["no_healing", "rule", "dqn"] = "rule"
    episodes: int = Field(default=4, ge=1, le=8)
    horizon: int = Field(default=10, ge=1, le=30)
    seed: int = Field(default=20000, ge=10000, le=2**30)


class EpisodeResponse(BaseModel):
    seed: int
    scenario: int
    reward: float
    recoveries: int
    metrics: MetricsResponse


class ExperimentResponse(BaseModel):
    id: str
    status: Literal["completed"] = "completed"
    requested_policy: str
    actual_policy: str
    seed: int
    episodes: int
    horizon: int
    mean_reward: float
    results: list[EpisodeResponse]
    created_at: str
    storage: Literal["in_memory"] = "in_memory"
    scope: Literal["local_simulator_evaluation"] = "local_simulator_evaluation"
    comparison_id: str | None = None
    environment_config: dict = Field(default_factory=dict)


class EventResponse(BaseModel):
    type: Literal["snapshot", "metrics", "alert", "healing", "error"]
    sequence: int
    timestamp: int
    data: dict


class DashboardResponse(BaseModel):
    project: str
    scope: str
    running: bool
    mode: str
    config: NetworkSettings
    metrics: MetricsResponse
    nodes: list[NodeResponse]
    consensus_health: float
    consensus: ConsensusResponse
    alerts: list[AlertResponse]
    recovery: list[HealingResponse]
    trust_audit: list[dict]
    transactions: list[TxPayload]
    blocks: list[BlockResponse]
    instance_id: str
    history: list[MetricsResponse]
    partitioned_links: list[list[str]]
    active_scenario: dict | None
    recent_events: list[dict]


class ScenarioRunRequest(Input):
    kind: Literal[
        "node_failure",
        "delay",
        "partition",
        "suspicious_voting",
        "sybil_like",
        "conflicting_transactions",
    ]
    node_id: str = Field(default="node_1", min_length=1, max_length=64)
    duration_rounds: int = Field(default=5, ge=1, le=20)
    latency_ms: int = Field(default=300, ge=0, le=5000)


class ScenarioRunResponse(BaseModel):
    id: str
    kind: str
    node_id: str
    duration_rounds: int
    started_at: int
    expires_at: int
    ended_at: int | None
    status: str
    details: dict
    scope: Literal["controlled_simulation"]


class TrustHistoryResponse(BaseModel):
    node_id: str
    evidence_id: str
    kind: str
    timestamp: int
    before: float
    decayed: float
    after: float
    delta: float
    confidence: float
    verified: bool
    provenance: str


class AuditEvent(BaseModel):
    id: str
    timestamp: int
    kind: str
    summary: str
    details: dict


class SessionResponse(BaseModel):
    role: Literal["viewer", "operator", "admin"]
    permissions: list[str]


class ComparisonRequest(Input):
    episodes: int = Field(default=4, ge=1, le=4)
    horizon: int = Field(default=10, ge=1, le=20)
    seed: int = Field(default=20000, ge=10000, le=2**30)


class ComparisonResponse(BaseModel):
    id: str
    experiments: list[ExperimentResponse]
    matched_configuration: bool = True


class BlockDetail(BaseModel):
    block: BlockResponse
    hash_valid: bool
    parent_valid: bool
    state_integrity: bool
    consensus: Literal["genesis", "verified", "unverified"]


class ModelMetadata(BaseModel):
    status: Literal["trained", "untrained", "missing_or_invalid"]
    updates: int
    architecture: list[int]
    live_policy: Literal["rule"] = "rule"
    automatic_deployment: bool = False


class TrainingEpisode(BaseModel):
    episode: int
    reward: float
    loss: float | None = None


class LearningResponse(BaseModel):
    run_id: str | None
    source: str
    training: list[TrainingEpisode]
    updates: int
    evaluation: list[dict]
    claim: str
    model: ModelMetadata
