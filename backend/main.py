"""Loopback research API; explicit in-memory state and guarded simulator mutations."""

import asyncio
import json
import logging
import os
import re
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import Depends, FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse
from starlette.exceptions import HTTPException

from ledgershield.core import Rejected
from ledgershield.network import NetworkConfig
from ledgershield.service import Service

from . import api
from .database import archive, open_store
from .security import RateLimiter, admin, configured_tokens, operator


class JSONFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": record.levelname,
                "message": record.getMessage(),
                **getattr(record, "fields", {}),
            }
        )


logger = logging.getLogger("ledgershield")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
logger.propagate = False

ORIGINS = {
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:8000",
    "http://localhost:8000",
}


def configured_service():
    return Service(
        NetworkConfig(
            seed=int(os.getenv("SIM_SEED", "42")),
            node_count=int(os.getenv("NODE_COUNT", "6")),
            validator_count=int(os.getenv("VALIDATOR_COUNT", "4")),
        ),
        os.getenv("RECOVERY_MODE", "observe_only"),
    )


async def ticker(app):
    while True:
        await asyncio.sleep(2)
        if not app.state.service.running:
            continue
        try:
            app.state.service.step()
            archive(app)
        except Exception:
            app.state.service.network.metrics["failed_requests"] += 1
            app.state.service.running = False
            logger.error("simulation_paused_after_service_error")


@asynccontextmanager
async def lifespan(app):
    app.state.service = configured_service()
    app.state.tokens = configured_tokens()
    app.state.limiter = RateLimiter()
    app.state.experiments = {}
    app.state.store = open_store()
    if app.state.store is not None:
        app.state.experiments = {
            r["id"]: r for r in reversed(app.state.store.list("experiment", 100))
        }
    app.state.evaluation_lock = asyncio.Lock()
    app.state.websocket_count = 0
    task = asyncio.create_task(ticker(app))
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        try:
            archive(app)
        finally:
            if app.state.store is not None:
                app.state.store.close()


app = FastAPI(
    title="LedgerShield Research API",
    version="1.0.0",
    lifespan=lifespan,
    description="Local simulator with explicitly in-memory state. Public reads; bearer-token "
    "operator/admin roles for mutations. No API training or automatic model deployment. "
    "WebSocket /api/v1/ws emits snapshot, metrics, alert and healing event envelopes.",
)
app.include_router(api.router)


def error_response(request, code, detail, status, headers=None):
    return JSONResponse(
        {
            "error": {
                "code": code,
                "detail": detail,
                "request_id": getattr(request.state, "request_id", ""),
            }
        },
        status_code=status,
        headers=headers,
    )


@app.middleware("http")
async def request_context(request: Request, call_next):
    candidate = request.headers.get("x-request-id", "")
    request.state.request_id = (
        candidate if re.fullmatch(r"[a-zA-Z0-9_-]{8,64}", candidate) else str(uuid4())
    )
    started = time.monotonic()
    try:
        if request.headers.get("origin") and request.headers["origin"] not in ORIGINS:
            response = error_response(
                request, "origin_denied", "Browser origin is not allowed", 403
            )
        else:
            response = await call_next(request)
    except Exception:
        # Never return exception text, stack traces, credentials or payload input.
        response = error_response(
            request, "service_unavailable", "The service could not complete this request", 503
        )
    if response.status_code >= 400:
        request.app.state.service.network.metrics["failed_requests"] += 1
    elif request.method == "POST":
        request.app.state.service.event(
            "api_mutation",
            "Authorized simulator request completed",
            {
                "route": getattr(request.scope.get("route"), "path", "unknown"),
                "request_id": request.state.request_id,
                "status": response.status_code,
            },
        )
        try:
            archive(request.app)
        except Exception:
            request.app.state.service.running = False
            logger.error("archive_write_failed")
            response = error_response(
                request,
                "archive_unavailable",
                "The action may have completed in memory; archive failed and simulation was paused",
                503,
            )
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["Cache-Control"] = "no-store"
    logger.info(
        "http_request",
        extra={
            "fields": {
                "request_id": request.state.request_id,
                "method": request.method,
                "path": getattr(request.scope.get("route"), "path", "unmatched"),
                "status": response.status_code,
                "duration_ms": round((time.monotonic() - started) * 1000, 3),
            }
        },
    )
    return response


@app.exception_handler(Rejected)
async def rejected(request, exc):
    status = (
        409
        if exc.code
        in (
            "duplicate_transaction",
            "nonce_conflict",
            "approval_not_pending",
            "scenario_already_active",
            "no_active_scenario",
        )
        else 400
    )
    if request.url.path.endswith("/health"):
        status = 503
    return error_response(request, exc.code, exc.code.replace("_", " "), status)


@app.exception_handler(RequestValidationError)
async def malformed(request, exc):
    if request.url.path in ("/transactions", "/api/v1/transactions"):
        net = request.app.state.service.network
        net.metrics["submitted"] += 1
        net.metrics["rejected"] += 1
    # Do not echo Pydantic's raw input or context, which could contain secrets.
    fields = [".".join(map(str, item["loc"])) for item in exc.errors()]
    return error_response(
        request, "malformed_input", "Invalid request fields: " + ", ".join(fields), 422
    )


@app.exception_handler(HTTPException)
async def http_error(request, exc):
    detail = exc.detail if isinstance(exc.detail, str) else "request_rejected"
    return error_response(
        request,
        detail if re.fullmatch(r"[a-z_]+", detail) else "http_error",
        detail,
        exc.status_code,
        exc.headers,
    )


@app.get("/", include_in_schema=False)
async def root():
    return {"message": "LedgerShield", "api": "/api/v1", "docs": "/docs"}


@app.get("/live", tags=["Health"])
async def live():
    return {"status": "alive"}


@app.get("/ready", tags=["Health"])
async def ready(request: Request):
    try:
        store = request.app.state.store
        if store is not None:
            store.ready()
        request.app.state.service.network.ledger.verify_chain()
    except Exception:
        raise HTTPException(503, detail="readiness_failed") from None
    return {"status": "ready", "archive": "database" if store is not None else "disabled"}


@app.get("/state", include_in_schema=False)
async def legacy_state(request: Request):
    return request.app.state.service.state()


@app.get("/metrics", response_class=PlainTextResponse, include_in_schema=False)
async def prometheus(request: Request):
    return (
        "\n".join(
            f"ledgershield_{k} {v}" for k, v in request.app.state.service.state()["metrics"].items()
        )
        + "\n"
    )


@app.get("/nodes", include_in_schema=False)
async def legacy_nodes(request: Request):
    return {"nodes": request.app.state.service.state()["nodes"]}


@app.get("/consensus", include_in_schema=False)
async def legacy_consensus(request: Request):
    svc = request.app.state.service
    return {"health": 100 * float(svc.network.last_round["committed"]), **svc.network.last_round}


# Protected aliases for existing local clients. No anonymous mutation bypass.
for path, endpoint, role, methods in (
    ("/health", api.health, None, ["GET"]),
    ("/transactions", api.submit_transaction, operator, ["POST"]),
    ("/simulation/transaction", api.demo, operator, ["POST"]),
    ("/simulation/step", api.step, operator, ["POST"]),
    ("/simulation/scenario", api.scenario, operator, ["POST"]),
    ("/simulation/reset", api.reset, admin, ["POST"]),
    ("/simulation/partition", api.partition, operator, ["POST"]),
    ("/recovery/mode", api.mode, admin, ["POST"]),
    ("/recovery/{action_id}/approve", api.approve, admin, ["POST"]),
):
    app.add_api_route(
        path,
        endpoint,
        methods=methods,
        include_in_schema=False,
        dependencies=[Depends(role)] if role else [],
    )


async def stream(ws, versioned):
    if ws.headers.get("origin") and ws.headers["origin"] not in ORIGINS:
        await ws.close(code=1008)
        return
    if ws.app.state.websocket_count >= 16:
        await ws.close(code=1013)
        return
    ws.app.state.websocket_count += 1
    await ws.accept()
    seq = 0
    seen_alerts, seen_actions = set(), {}
    current_service = None
    try:
        while True:
            svc = ws.app.state.service
            if svc is not current_service:
                seen_alerts, seen_actions = set(), {}
                current_service = svc
            snapshot = svc.state()
            if not versioned:
                await ws.send_json(snapshot)
            else:
                events = [("snapshot", snapshot), ("metrics", snapshot["metrics"])]
                for alert in snapshot["alerts"]:
                    if alert["id"] not in seen_alerts:
                        events.append(("alert", alert))
                        seen_alerts.add(alert["id"])
                for record in snapshot["recovery"]:
                    if seen_actions.get(record["id"]) != record["status"]:
                        events.append(("healing", record))
                        seen_actions[record["id"]] = record["status"]
                for event_type, data in events:
                    seq += 1
                    await ws.send_json(
                        {
                            "type": event_type,
                            "sequence": seq,
                            "timestamp": svc.network.tick,
                            "data": data,
                        }
                    )
            try:
                await asyncio.wait_for(ws.receive_text(), timeout=1)
            except asyncio.TimeoutError:
                pass
    except (WebSocketDisconnect, RuntimeError):
        pass
    except Exception:
        logger.error("websocket_service_error")
        await ws.close(code=1011, reason="service_unavailable")
    finally:
        ws.app.state.websocket_count -= 1


@app.websocket("/api/v1/ws")
async def versioned_websocket(ws: WebSocket):
    await stream(ws, versioned=True)


@app.websocket("/ws/dashboard")
async def legacy_websocket(ws: WebSocket):
    await stream(ws, versioned=False)
