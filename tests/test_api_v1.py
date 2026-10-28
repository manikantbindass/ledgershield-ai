import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend import api

ADMIN = "test-admin-" + "a" * 40
OPERATOR = "test-operator-" + "b" * 40
ADMIN_HEADERS = {"Authorization": f"Bearer {ADMIN}"}
OPERATOR_HEADERS = {"Authorization": f"Bearer {OPERATOR}"}
PREFIX = "/api/v1"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("LEDGERSHIELD_ADMIN_TOKEN", ADMIN)
    monkeypatch.setenv("LEDGERSHIELD_OPERATOR_TOKEN", OPERATOR)
    with TestClient(app) as client:
        yield client


def post(client, path, body=None, headers=None):
    return client.post(PREFIX + path, json=body or {}, headers=headers or ADMIN_HEADERS)


@pytest.mark.parametrize("path", ["/health", "/metrics", "/network/overview", "/network/state",
                                  "/nodes", "/nodes/node_0", "/blocks", "/transactions", "/alerts",
                                  "/trust/scores", "/healing/actions", "/experiments"])
def test_public_reads_are_backed_and_typed(client, path):
    response = client.get(PREFIX + path)
    assert response.status_code == 200
    assert response.headers["x-request-id"]
    assert response.headers["cache-control"] == "no-store"
    if path == "/blocks":
        assert response.json()["items"][0]["index"] == 0
    if path == "/nodes/node_0":
        assert len(response.json()["identity"]) == 64


@pytest.mark.parametrize("path", ["/nodes/missing", "/healing/actions/missing", "/experiments/missing"])
def test_not_found(client, path):
    response = client.get(PREFIX + path)
    assert response.status_code == 404
    assert response.json()["error"]["request_id"] == response.headers["x-request-id"]


def test_pagination_and_query_validation(client):
    response = client.get(PREFIX + "/nodes?offset=1&limit=2").json()
    assert response["total"] == 6
    assert [node["id"] for node in response["items"]] == ["node_1", "node_2"]
    assert response["storage"] == "in_memory"
    assert client.get(PREFIX + "/nodes?limit=101").status_code == 422
    assert client.get(PREFIX + "/nodes?offset=-1").status_code == 422
    assert client.get(PREFIX + "/nodes?offset=100").json()["items"] == []


@pytest.mark.parametrize("path", ["/simulation/start", "/simulation/stop", "/simulation/step",
                                  "/simulation/transaction", "/simulation/scenarios", "/simulation/reset",
                                  "/simulation/partition", "/healing/mode", "/policies/evaluate"])
def test_sensitive_routes_require_authentication(client, path):
    response = client.post(PREFIX + path, json={})
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert client.post(PREFIX + path, json={}, headers={"Authorization": "Bearer invalid"}).status_code == 401


def test_rbac_and_legacy_aliases_cannot_bypass(client):
    assert post(client, "/simulation/reset", headers=OPERATOR_HEADERS).status_code == 403
    assert post(client, "/healing/mode", {"mode": "autonomous_simulation"}, OPERATOR_HEADERS).status_code == 403
    assert client.post("/simulation/step").status_code == 401
    assert client.post("/simulation/reset", json={}, headers=OPERATOR_HEADERS).status_code == 403
    assert post(client, "/simulation/start", headers=OPERATOR_HEADERS).json()["running"]
    assert not post(client, "/simulation/stop", headers=OPERATOR_HEADERS).json()["running"]


def test_scenario_ledger_evidence_and_action_detail(client):
    result = post(client, "/simulation/scenarios", {"node_id": "node_1", "behavior": "malicious"})
    assert result.status_code == 201 and result.json()["applied"]
    assert len(app.state.service.scenarios) == 1
    tx = post(client, "/simulation/transaction").json()
    assert client.get(PREFIX + "/transactions").json()["items"][0]["status"] == "pending"
    assert post(client, "/transactions", tx).status_code == 409
    assert post(client, "/simulation/step").status_code == 200
    history = client.get(PREFIX + "/transactions").json()["items"]
    assert history[0]["status"] == "committed" and history[0]["committed_at"] == 1
    alerts = client.get(PREFIX + "/alerts").json()["items"]
    assert any(a["verified"] for a in alerts)
    actions = client.get(PREFIX + "/healing/actions").json()["items"]
    assert actions and actions[0]["status"] == "observed"
    assert client.get(PREFIX + "/healing/actions/" + actions[0]["id"]).status_code == 200
    assert client.get(PREFIX + "/metrics").json()["committed_transactions"] == 1


def test_malformed_input_does_not_echo_secrets(client):
    secret = "private-key-do-not-echo"
    response = post(client, "/transactions", {"signature": secret, "private_key": secret})
    assert response.status_code == 422 and secret not in response.text
    assert post(client, "/simulation/scenarios", {"node_id": "unknown", "behavior": "honest"}).status_code == 404
    assert post(client, "/simulation/scenarios", {"node_id": "node_1", "behavior": "other"}).status_code == 422
    assert post(client, "/policies/evaluate", {"episodes": 999}).status_code == 422
    assert post(client, "/policies/evaluate", {"model_path": secret}).status_code == 422


def test_evaluation_records_real_isolated_results_and_rate_limits(client, monkeypatch):
    monkeypatch.setenv("LEDGERSHIELD_MODEL_PATH", "artifacts/nonexistent-checkpoint.json")
    before = app.state.service.network.snapshot()
    response = post(client, "/policies/evaluate", {"policy": "dqn", "episodes": 2, "horizon": 2})
    assert response.status_code == 201
    experiment = response.json()
    assert experiment["actual_policy"] == "rule_fallback"
    assert experiment["results"][0]["metrics"]["submitted"] == 2
    assert app.state.service.network.tick == before["tick"]
    assert client.get(PREFIX + "/experiments/" + experiment["id"]).json() == experiment
    assert client.get(PREFIX + "/experiments").json()["total"] == 1
    for _ in range(2):
        assert post(client, "/policies/evaluate", {"episodes": 1, "horizon": 1}).status_code == 201
    limited = post(client, "/policies/evaluate", {"episodes": 1, "horizon": 1})
    assert limited.status_code == 429 and int(limited.headers["retry-after"]) > 0


def test_sanitized_service_error_and_request_ids(client, monkeypatch):
    def broken():
        raise RuntimeError("secret-server-path-and-private-token")
    monkeypatch.setattr(app.state.service, "state", broken)
    response = client.get(PREFIX + "/metrics", headers={"X-Request-ID": "research-request-123"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"
    assert response.headers["x-request-id"] == "research-request-123"
    assert "secret-server" not in response.text and "Traceback" not in response.text


def test_evaluation_failure_and_concurrency_guard(client, monkeypatch):
    class BusyLock:
        def locked(self):
            return True
    original = app.state.evaluation_lock
    app.state.evaluation_lock = BusyLock()
    assert post(client, "/policies/evaluate", {"episodes": 1, "horizon": 1}).status_code == 409
    app.state.evaluation_lock = original
    def broken(_):
        raise RuntimeError("private-model-path")
    monkeypatch.setattr(api, "evaluate", broken)
    response = post(client, "/policies/evaluate", {"episodes": 1, "horizon": 1})
    assert response.status_code == 503 and "private-model-path" not in response.text
    assert not app.state.experiments


def test_websocket_events_and_openapi_security(client):
    post(client, "/simulation/scenarios", {"node_id": "node_1", "behavior": "malicious"})
    post(client, "/simulation/step")
    with client.websocket_connect(PREFIX + "/ws") as ws:
        events = [ws.receive_json() for _ in range(4)]
        assert [e["sequence"] for e in events] == [1, 2, 3, 4]
        assert events[0]["type"] == "snapshot" and events[1]["type"] == "metrics"
        assert any(e["type"] == "alert" for e in events)
        # Additional alerts can precede the first healing event.
        kinds = {e["type"] for e in events}
        for _ in range(8):
            if "healing" in kinds:
                break
            kinds.add(ws.receive_json()["type"])
        assert "healing" in kinds
    schema = client.get("/openapi.json").json()
    assert schema["paths"][PREFIX + "/simulation/start"]["post"]["security"]
    assert "Page_NodeResponse_" in schema["components"]["schemas"]
    assert "private_key" not in str(schema["components"]["schemas"])


def test_auth_unconfigured_disables_mutations(monkeypatch):
    monkeypatch.delenv("LEDGERSHIELD_ADMIN_TOKEN", raising=False)
    monkeypatch.delenv("LEDGERSHIELD_OPERATOR_TOKEN", raising=False)
    with TestClient(app) as client:
        assert client.post(PREFIX + "/simulation/start").status_code == 503
        assert client.get(PREFIX + "/health").status_code == 200
