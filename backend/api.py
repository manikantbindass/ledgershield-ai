"""Versioned API over the shared local service and bounded experiment store."""
import asyncio
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from ledgershield.core import Rejected, Transaction
from ledgershield.network import NetworkConfig
from ledgershield.recovery import RecoveryConfig
from ledgershield.service import Service
from . import models as m
from .evaluation import evaluate
from .security import admin, operator

ERRORS = {code: {"model": m.ErrorResponse} for code in (400, 401, 403, 404, 409, 422, 429, 503)}
router = APIRouter(prefix="/api/v1", responses=ERRORS)


def paginate(items, offset, limit):
    return {"items": items[offset:offset + limit], "total": len(items),
            "offset": offset, "limit": limit, "storage": "in_memory"}


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


@router.get("/network/state", response_model=m.DashboardResponse, tags=["Network"],
            description="Bounded dashboard snapshot; use paginated collections for complete history.")
async def dashboard(request: Request):
    return service(request).state()


@router.get("/nodes/{node_id}", response_model=m.NodeResponse, tags=["Network"])
async def node(node_id: str, request: Request):
    for item in service(request).state()["nodes"]:
        if item["id"] == node_id:
            return item
    raise HTTPException(404, detail="node_not_found")


@router.get("/blocks", response_model=m.Page[m.BlockResponse], tags=["Ledger"])
async def blocks(request: Request, page=Depends(pagination)):
    return paginate([b.to_dict() for b in service(request).network.ledger.chain], *page)


@router.get("/transactions", response_model=m.Page[m.TransactionResponse], tags=["Ledger"])
async def transactions(request: Request, page=Depends(pagination)):
    return paginate(list(service(request).network.transaction_records.values()), *page)


@router.post("/transactions", response_model=m.AcceptedResponse, status_code=202,
             dependencies=[Depends(operator)], tags=["Ledger"])
async def submit_transaction(payload: m.TxPayload, request: Request):
    tx = Transaction(**payload.model_dump())
    service(request).network.submit(tx)
    return {"tx_hash": tx.tx_hash}


@router.get("/alerts", response_model=m.Page[m.AlertResponse], tags=["Evidence"])
async def alerts(request: Request, page=Depends(pagination)):
    return paginate(service(request).detector.alerts, *page)


@router.get("/trust/scores", response_model=m.Page[m.TrustResponse], tags=["Evidence"])
async def trust(request: Request, page=Depends(pagination)):
    svc = service(request)
    cfg = svc.trust.config
    items = [{"node_id": name, "score": svc.trust.get(name), "initial": cfg.initial,
              "minimum": cfg.minimum, "maximum": cfg.maximum, "threshold": cfg.threshold,
              "updated_at": svc.trust.updated.get(name),
              "evidence_count": sum(row["node_id"] == name for row in svc.trust.audit)}
             for name in svc.network.nodes]
    return paginate(items, *page)


@router.get("/healing/actions", response_model=m.Page[m.HealingResponse], tags=["Recovery"])
async def actions(request: Request, page=Depends(pagination)):
    return paginate(service(request).recovery.audit, *page)


@router.get("/healing/actions/{action_id}", response_model=m.HealingResponse, tags=["Recovery"])
async def action(action_id: str, request: Request):
    record = service(request).recovery.records.get(action_id)
    if record is None:
        raise HTTPException(404, detail="action_not_found")
    return record


@router.post("/healing/actions/{action_id}/approve", response_model=m.HealingResponse,
             dependencies=[Depends(admin)], tags=["Recovery"])
async def approve(action_id: str, request: Request):
    if action_id not in service(request).recovery.records:
        raise HTTPException(404, detail="action_not_found")
    return service(request).recovery.approve(action_id)


@router.post("/healing/mode", response_model=m.Mode, dependencies=[Depends(admin)], tags=["Recovery"])
async def mode(payload: m.Mode, request: Request):
    service(request).recovery.config = RecoveryConfig(mode=payload.mode)
    return payload


@router.post("/simulation/scenarios", response_model=m.ScenarioResponse, status_code=201,
             dependencies=[Depends(operator)], tags=["Simulation"])
async def scenario(payload: m.Scenario, request: Request):
    svc = service(request)
    if payload.node_id not in svc.network.nodes:
        raise HTTPException(404, detail="node_not_found")
    svc.network.nodes[payload.node_id].behavior = payload.behavior
    record = {"id": str(uuid4()), "timestamp": svc.network.tick,
              "applied": True, **payload.model_dump()}
    svc.scenarios.append(record)
    return record


@router.post("/simulation/start", response_model=m.OverviewResponse,
             dependencies=[Depends(operator)], tags=["Simulation"])
async def start(request: Request):
    service(request).running = True
    return service(request).state()


@router.post("/simulation/stop", response_model=m.OverviewResponse,
             dependencies=[Depends(operator)], tags=["Simulation"])
async def stop(request: Request):
    service(request).running = False
    return service(request).state()


@router.post("/simulation/step", response_model=m.OverviewResponse,
             dependencies=[Depends(operator)], tags=["Simulation"])
async def step(request: Request):
    service(request).step()
    return service(request).state()


@router.post("/simulation/transaction", response_model=m.TxPayload, status_code=202,
             dependencies=[Depends(operator)], tags=["Simulation"])
async def demo(request: Request):
    return service(request).network.demo_transaction().to_dict()


@router.post("/simulation/reset", response_model=m.OverviewResponse,
             dependencies=[Depends(admin)], tags=["Simulation"])
async def reset(payload: m.Reset, request: Request):
    request.app.state.service = Service(NetworkConfig(**payload.model_dump()))
    return service(request).state()


@router.post("/simulation/partition", response_model=m.PartitionResponse,
             dependencies=[Depends(operator)], tags=["Simulation"])
async def partition(payload: m.Partition, request: Request):
    net = service(request).network
    if payload.groups:
        net.partition(payload.groups)
    else:
        net.partitions.clear()
    return {"partitioned_links": len(net.partitions)}


@router.post("/policies/evaluate", response_model=m.ExperimentResponse, status_code=201, tags=["Experiments"])
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
async def experiments(request: Request, page=Depends(pagination)):
    return paginate(list(request.app.state.experiments.values()), *page)


@router.get("/experiments/{experiment_id}", response_model=m.ExperimentResponse, tags=["Experiments"])
async def experiment(experiment_id: str, request: Request):
    result = request.app.state.experiments.get(experiment_id)
    if result is None:
        raise HTTPException(404, detail="experiment_not_found")
    return result
