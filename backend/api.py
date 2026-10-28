"""Versioned API over the shared local service and bounded experiment store."""

import asyncio
from dataclasses import asdict
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.security import HTTPAuthorizationCredentials

from ledgershield.core import Transaction
from ledgershield.network import NetworkConfig
from ledgershield.recovery import RecoveryConfig
from ledgershield.service import Service

from . import models as m
from .evaluation import evaluate
from .research import learning_report
from .security import admin, bearer, operator, principal

ERRORS = {code: {"model": m.ErrorResponse} for code in (400, 401, 403, 404, 409, 422, 429, 503)}
router = APIRouter(prefix="/api/v1", responses=ERRORS)


def paginate(items, offset, limit):
    return {
        "items": items[offset : offset + limit],
        "total": len(items),
        "offset": offset,
        "limit": limit,
        "storage": "in_memory",
    }


def matching(items, query, fields):
    query = query.casefold().strip()
    return [
        item
        for item in items
        if not query or any(query in str(item.get(field, "")).casefold() for field in fields)
    ]


async def pagination(offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)):
    return offset, limit


def service(request):
    return request.app.state.service


@router.get("/health", response_model=m.HealthResponse, tags=["Health"])
async def health(request: Request):
    svc = service(request)
    if not svc.network.ledger.verify_chain():
        raise HTTPException(503, detail="integrity_check_failed")
    return {"integrity": True, "running": svc.running}


@router.get("/metrics", response_model=m.MetricsResponse, tags=["Telemetry"])
async def metrics(request: Request):
    return service(request).state()["metrics"]


@router.get("/network/overview", response_model=m.OverviewResponse, tags=["Network"])
async def overview(request: Request):
    return service(request).state()


@router.get("/nodes", response_model=m.Page[m.NodeResponse], tags=["Network"])
async def nodes(request: Request, page=Depends(pagination)):
    return paginate(service(request).state()["nodes"], *page)


@router.get(
    "/network/state",
    response_model=m.DashboardResponse,
    tags=["Network"],
    description="Bounded dashboard snapshot; use paginated collections for complete history.",
)
async def dashboard(request: Request):
    return service(request).state()


@router.get("/nodes/{node_id}", response_model=m.NodeResponse, tags=["Network"])
async def node(node_id: str, request: Request):
    for item in service(request).state()["nodes"]:
        if item["id"] == node_id:
            return item
    raise HTTPException(404, detail="node_not_found")


@router.get("/blocks", response_model=m.Page[m.BlockResponse], tags=["Ledger"])
async def blocks(request: Request, page=Depends(pagination), q: str = Query("", max_length=100)):
    return paginate(
        matching(
            [b.to_dict() for b in service(request).network.ledger.chain],
            q,
            ("index", "hash", "validator"),
        ),
        *page,
    )


@router.get("/transactions", response_model=m.Page[m.TransactionResponse], tags=["Ledger"])
async def transactions(
    request: Request, page=Depends(pagination), q: str = Query("", max_length=100)
):
    return paginate(
        matching(
            list(service(request).network.transaction_records.values()),
            q,
            ("tx_hash", "status", "rejection_code"),
        ),
        *page,
    )


@router.post(
    "/transactions",
    response_model=m.AcceptedResponse,
    status_code=202,
    dependencies=[Depends(operator)],
    tags=["Ledger"],
)
async def submit_transaction(payload: m.TxPayload, request: Request):
    tx = Transaction(**payload.model_dump())
    service(request).network.submit(tx)
    return {"tx_hash": tx.tx_hash}


@router.get("/alerts", response_model=m.Page[m.AlertResponse], tags=["Evidence"])
async def alerts(request: Request, page=Depends(pagination), q: str = Query("", max_length=100)):
    return paginate(
        matching(service(request).detector.alerts, q, ("node_id", "method", "severity", "id")),
        *page,
    )


@router.get("/trust/scores", response_model=m.Page[m.TrustResponse], tags=["Evidence"])
async def trust(request: Request, page=Depends(pagination)):
    svc = service(request)
    cfg = svc.trust.config
    items = [
        {
            "node_id": name,
            "score": svc.trust.get(name),
            "initial": cfg.initial,
            "minimum": cfg.minimum,
            "maximum": cfg.maximum,
            "threshold": cfg.threshold,
            "updated_at": svc.trust.updated.get(name),
            "evidence_count": sum(row["node_id"] == name for row in svc.trust.audit),
        }
        for name in svc.network.nodes
    ]
    return paginate(items, *page)


@router.get("/healing/actions", response_model=m.Page[m.HealingResponse], tags=["Recovery"])
async def actions(request: Request, page=Depends(pagination), q: str = Query("", max_length=100)):
    return paginate(
        matching(service(request).recovery.audit, q, ("node_id", "action", "status", "id")), *page
    )


@router.get("/healing/actions/{action_id}", response_model=m.HealingResponse, tags=["Recovery"])
async def action(action_id: str, request: Request):
    record = service(request).recovery.records.get(action_id)
    if record is None:
        raise HTTPException(404, detail="action_not_found")
    return record


@router.post(
    "/healing/actions/{action_id}/approve",
    response_model=m.HealingResponse,
    dependencies=[Depends(admin)],
    tags=["Recovery"],
)
async def approve(action_id: str, request: Request):
    if action_id not in service(request).recovery.records:
        raise HTTPException(404, detail="action_not_found")
    return service(request).recovery.approve(action_id)


@router.post(
    "/healing/mode", response_model=m.Mode, dependencies=[Depends(admin)], tags=["Recovery"]
)
async def mode(payload: m.Mode, request: Request):
    service(request).recovery.config = RecoveryConfig(mode=payload.mode)
    return payload


@router.post(
    "/simulation/scenarios",
    response_model=m.ScenarioResponse,
    status_code=201,
    dependencies=[Depends(operator)],
    tags=["Simulation"],
)
async def scenario(payload: m.Scenario, request: Request):
    svc = service(request)
    if svc.scenario_runs.active:
        raise HTTPException(409, detail="scenario_already_active")
    if payload.node_id not in svc.network.nodes:
        raise HTTPException(404, detail="node_not_found")
    svc.network.nodes[payload.node_id].behavior = payload.behavior
    record = {
        "id": str(uuid4()),
        "timestamp": svc.network.tick,
        "applied": True,
        **payload.model_dump(),
    }
    svc.scenarios.append(record)
    return record


@router.post(
    "/simulation/start",
    response_model=m.OverviewResponse,
    dependencies=[Depends(operator)],
    tags=["Simulation"],
)
async def start(request: Request):
    service(request).running = True
    return service(request).state()


@router.post(
    "/simulation/stop",
    response_model=m.OverviewResponse,
    dependencies=[Depends(operator)],
    tags=["Simulation"],
)
async def stop(request: Request):
    service(request).running = False
    return service(request).state()


@router.post(
    "/simulation/step",
    response_model=m.OverviewResponse,
    dependencies=[Depends(operator)],
    tags=["Simulation"],
)
async def step(request: Request):
    service(request).step()
    return service(request).state()


@router.post(
    "/simulation/transaction",
    response_model=m.TxPayload,
    status_code=202,
    dependencies=[Depends(operator)],
    tags=["Simulation"],
)
async def demo(request: Request):
    return service(request).network.demo_transaction().to_dict()


@router.post(
    "/simulation/reset",
    response_model=m.OverviewResponse,
    dependencies=[Depends(admin)],
    tags=["Simulation"],
)
async def reset(payload: m.Reset, request: Request):
    request.app.state.service = Service(NetworkConfig(**payload.model_dump()))
    return service(request).state()


@router.post(
    "/simulation/partition",
    response_model=m.PartitionResponse,
    dependencies=[Depends(operator)],
    tags=["Simulation"],
)
async def partition(payload: m.Partition, request: Request):
    net = service(request).network
    if service(request).scenario_runs.active:
        raise HTTPException(409, detail="scenario_already_active")
    if payload.groups:
        net.partition(payload.groups)
    else:
        net.partitions.clear()
    return {"partitioned_links": len(net.partitions)}


@router.post(
    "/policies/evaluate", response_model=m.ExperimentResponse, status_code=201, tags=["Experiments"]
)
async def policy_evaluation(payload: m.EvaluationRequest, request: Request, role=Depends(operator)):
    state = request.app.state
    state.limiter.check(role, "evaluation", limit=3)
    if state.evaluation_lock.locked():
        raise HTTPException(409, detail="evaluation_in_progress")
    async with state.evaluation_lock:
        # Bounded 8x30 steps; isolated state; no paths or arbitrary code in request.
        record = await asyncio.to_thread(evaluate, payload)
        state.experiments[record["id"]] = record
        if len(state.experiments) > 100:
            state.experiments.pop(next(iter(state.experiments)))
        return record


@router.get("/experiments", response_model=m.Page[m.ExperimentResponse], tags=["Experiments"])
async def experiments(
    request: Request, page=Depends(pagination), q: str = Query("", max_length=100)
):
    return paginate(
        matching(
            list(request.app.state.experiments.values()),
            q,
            ("id", "actual_policy", "comparison_id"),
        ),
        *page,
    )


@router.get(
    "/experiments/{experiment_id}", response_model=m.ExperimentResponse, tags=["Experiments"]
)
async def experiment(experiment_id: str, request: Request):
    result = request.app.state.experiments.get(experiment_id)
    if result is None:
        raise HTTPException(404, detail="experiment_not_found")
    return result


@router.get("/auth/session", response_model=m.SessionResponse, tags=["Access"])
async def session(
    request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)
):
    role = await principal(request, credentials) if credentials else "viewer"
    permissions = [] if role == "viewer" else ["simulate", "evaluate", "submit_transactions"]
    if role == "admin":
        permissions += ["approve", "configure", "reset"]
    return {"role": role, "permissions": permissions}


@router.get("/trust/history", response_model=m.Page[m.TrustHistoryResponse], tags=["Evidence"])
async def trust_history(
    request: Request,
    page=Depends(pagination),
    q: str = Query("", max_length=100),
    node_id: str = Query("", max_length=64),
):
    rows = [
        r for r in reversed(service(request).trust.audit) if not node_id or r["node_id"] == node_id
    ]
    return paginate(matching(rows, q, ("node_id", "kind", "evidence_id")), *page)


@router.get("/audit/events", response_model=m.Page[m.AuditEvent], tags=["Evidence"])
async def events(request: Request, page=Depends(pagination), q: str = Query("", max_length=100)):
    return paginate(
        matching(list(reversed(service(request).events)), q, ("kind", "summary", "id")), *page
    )


@router.get("/settings", tags=["Settings"])
async def settings(request: Request):
    svc = service(request)
    return {
        "storage": "in_memory",
        "archive": "database" if request.app.state.store is not None else "disabled",
        "trust": asdict(svc.trust.config),
        "recovery": asdict(svc.recovery.config),
        "network": asdict(svc.network.config),
        "limits": {
            "scenario_rounds": 20,
            "evaluations_per_minute_per_role": 3,
            "mutation_requests_per_minute_per_role": 60,
            "history_samples": 240,
            "audit_events": 500,
        },
        "live_policy": "rule",
    }


@router.get("/blocks/{height}", response_model=m.BlockDetail, tags=["Ledger"])
async def block_detail(height: int, request: Request):
    net = service(request).network
    if not 0 <= height < len(net.ledger.chain):
        raise HTTPException(404, detail="block_not_found")
    block = net.ledger.chain[height]
    consensus = "genesis" if height == 0 else "unverified"
    if height:
        certificate = next((c for c in net.certificates if c["height"] == height), None)
        if certificate and all(
            net.verify_certificate(block, certificate[p], p, certificate["view"])
            for p in ("prepare", "commit")
        ):
            consensus = "verified"
    return {
        "block": block.to_dict(),
        "hash_valid": block.hash == block.compute_hash(),
        "parent_valid": block.previous_hash
        == (net.ledger.chain[height - 1].hash if height else "0" * 64),
        "state_integrity": net.ledger.verify_chain(),
        "consensus": consensus,
    }


@router.get("/learning/runs", response_model=m.LearningResponse, tags=["Experiments"])
async def learning():
    return learning_report()


@router.post(
    "/policies/compare", response_model=m.ComparisonResponse, status_code=201, tags=["Experiments"]
)
async def compare(payload: m.ComparisonRequest, request: Request, role=Depends(operator)):
    state = request.app.state
    state.limiter.check(role, "evaluation", limit=3)
    if state.evaluation_lock.locked():
        raise HTTPException(409, detail="evaluation_in_progress")
    async with state.evaluation_lock:

        def work():
            return [
                evaluate(m.EvaluationRequest(policy=policy, **payload.model_dump()))
                for policy in ("no_healing", "rule", "dqn")
            ]

        records = await asyncio.to_thread(work)
        comparison_id = str(uuid4())
        for record in records:
            record["comparison_id"] = comparison_id
            state.experiments[record["id"]] = record
        while len(state.experiments) > 100:
            state.experiments.pop(next(iter(state.experiments)))
        service(request).event(
            "evaluation", "Matched policy comparison completed", {"comparison_id": comparison_id}
        )
        return {"id": comparison_id, "experiments": records, "matched_configuration": True}


@router.get("/simulation/runs", response_model=m.Page[m.ScenarioRunResponse], tags=["Simulation"])
async def scenario_runs(request: Request, page=Depends(pagination)):
    return paginate(list(reversed(service(request).scenario_runs.runs)), *page)


@router.post(
    "/simulation/runs",
    response_model=m.ScenarioRunResponse,
    status_code=201,
    dependencies=[Depends(operator)],
    tags=["Simulation"],
)
async def run_scenario(payload: m.ScenarioRunRequest, request: Request):
    return service(request).scenario_runs.start(payload)


@router.post(
    "/simulation/runs/{run_id}/stop",
    response_model=m.ScenarioRunResponse,
    dependencies=[Depends(operator)],
    tags=["Simulation"],
)
async def stop_scenario(run_id: str, request: Request):
    runs = service(request).scenario_runs
    record = next((r for r in runs.runs if r["id"] == run_id), None)
    if record is None:
        raise HTTPException(404, detail="scenario_not_found")
    return runs.stop() if record["status"] == "running" else record


@router.get("/archive/{kind}", tags=["Evidence"])
async def archived(kind: str, request: Request, page=Depends(pagination)):
    if kind not in ("snapshot", "event", "healing", "experiment"):
        raise HTTPException(404, detail="archive_kind_not_found")
    store = request.app.state.store
    if store is None:
        raise HTTPException(503, detail="archive_unconfigured")
    rows = store.list(kind, 1000)
    result = paginate(rows, *page)
    result["storage"] = "database_archive"
    return result
