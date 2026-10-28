import pytest
from fastapi.testclient import TestClient

from backend import research
from backend.main import app
from backend.models import ScenarioRunRequest
from ledgershield.core import Rejected
from ledgershield.service import Service

TOKEN = "phase9-test-admin-" + "x" * 40
HEADERS = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("LEDGERSHIELD_ADMIN_TOKEN", TOKEN)
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize(
    "kind",
    [
        "node_failure",
        "delay",
        "partition",
        "suspicious_voting",
        "sybil_like",
        "conflicting_transactions",
    ],
)
def test_scenarios_apply_expire_and_preserve_ledger(kind):
    svc = Service()
    original_membership = svc.network.validators
    record = svc.scenario_runs.start(ScenarioRunRequest(kind=kind, duration_rounds=2))
    assert svc.running and record["status"] == "running"
    if kind == "sybil_like":
        assert len(svc.network.nodes) == 9
        assert all(
            not svc.network.nodes[name].validator for name in record["details"]["identities"]
        )
    if kind == "conflicting_transactions":
        assert record["details"]["result"] == "nonce_conflict"
        assert svc.network.metrics["accepted"] == 1 and svc.network.metrics["rejected"] == 1
    svc.step()
    svc.step()
    assert record["status"] == "completed" and svc.scenario_runs.active is None
    assert len(svc.network.nodes) == 6 and svc.network.validators == original_membership
    assert svc.network.config.latency_ms == 20 and not svc.network.partitions
    assert svc.network.nodes["node_1"].behavior == "honest" and not svc.running
    assert svc.network.ledger.verify_chain()
    assert svc.history and svc.events


def test_only_one_active_scenario_and_stop_restores_previous_running_state():
    svc = Service()
    svc.running = True
    run = svc.scenario_runs.start(ScenarioRunRequest(kind="delay", duration_rounds=10))
    with pytest.raises(Rejected, match="scenario_already_active"):
        svc.scenario_runs.start(ScenarioRunRequest(kind="node_failure"))
    svc.step()
    tick = svc.network.tick
    svc.scenario_runs.stop()
    assert run["status"] == "stopped" and svc.running
    assert svc.network.tick == tick  # Fault cleanup never rewinds measured history.


def test_session_and_protected_scenario_routes(client):
    assert client.get("/api/v1/auth/session").json()["role"] == "viewer"
    assert client.get("/api/v1/auth/session", headers=HEADERS).json()["role"] == "admin"
    assert (
        client.get(
            "/api/v1/auth/session", headers={"Authorization": "Bearer incorrect"}
        ).status_code
        == 401
    )
    for endpoint in ("/simulation/runs", "/policies/compare"):
        assert client.post("/api/v1" + endpoint, json={}).status_code == 401
    response = client.post(
        "/api/v1/simulation/runs",
        headers=HEADERS,
        json={"kind": "sybil_like", "duration_rounds": 2},
    )
    assert response.status_code == 201
    run_id = response.json()["id"]
    assert (
        client.post("/api/v1/simulation/runs", headers=HEADERS, json={"kind": "delay"}).status_code
        == 409
    )
    for _ in range(2):
        assert (
            client.post(f"/api/v1/simulation/runs/{run_id}/stop", headers=HEADERS).status_code
            == 200
        )
    assert client.get("/api/v1/simulation/runs").json()["total"] == 1
    assert (
        client.post(
            "/api/v1/simulation/runs",
            headers=HEADERS,
            json={"kind": "delay", "duration_rounds": 21},
        ).status_code
        == 422
    )


def test_matched_comparison_reports_real_config_and_isolated_state(client):
    before = app.state.service.network.tick
    response = client.post(
        "/api/v1/policies/compare",
        headers=HEADERS,
        json={"episodes": 2, "horizon": 2, "seed": 24000},
    )
    assert response.status_code == 201
    data = response.json()
    assert len(data["experiments"]) == 3
    assert len({r["comparison_id"] for r in data["experiments"]}) == 1
    assert len({(r["seed"], r["episodes"], r["horizon"]) for r in data["experiments"]}) == 1
    assert all(r["environment_config"]["validator_count"] == 4 for r in data["experiments"])
    assert app.state.service.network.tick == before
    assert client.get("/api/v1/experiments").json()["total"] == 3


def test_block_certificate_trust_history_and_search(client):
    client.post("/api/v1/simulation/transaction", headers=HEADERS)
    client.post("/api/v1/simulation/step", headers=HEADERS)
    block = client.get("/api/v1/blocks/1").json()
    assert block["hash_valid"] and block["parent_valid"] and block["state_integrity"]
    assert block["consensus"] == "verified"
    assert client.get("/api/v1/blocks/9999").status_code == 404
    assert client.get("/api/v1/blocks?q=node_0").json()["total"] == 1
    assert client.get("/api/v1/transactions?q=committed").json()["total"] == 1
    history = client.get("/api/v1/trust/history?node_id=node_0").json()
    assert history["total"] and all(row["node_id"] == "node_0" for row in history["items"])
    settings = client.get("/api/v1/settings")
    assert TOKEN not in settings.text and "TOKEN" not in settings.text
    events = client.get("/api/v1/audit/events").json()
    assert events["total"] and any(row["kind"] == "api_mutation" for row in events["items"])
    snapshot = client.get("/api/v1/network/state").json()
    assert snapshot["history"] and snapshot["instance_id"]


def test_missing_learning_artifacts_are_explicit(client, tmp_path, monkeypatch):
    monkeypatch.setattr(research, "ROOT", tmp_path)
    monkeypatch.setenv("LEDGERSHIELD_MODEL_PATH", str(tmp_path / "missing.json"))
    report = client.get("/api/v1/learning/runs").json()
    assert report["run_id"] is None and not report["training"]
    assert report["model"]["status"] == "missing_or_invalid"
    assert not report["model"]["automatic_deployment"]


def test_participation_remains_bounded_across_failed_views():
    svc = Service()
    svc.network.nodes["node_1"].behavior = "unavailable"
    svc.network.nodes["node_2"].behavior = "faulty"
    for _ in range(3):
        svc.step()
    assert 0 <= svc.network.summary()["participation"] <= 1
