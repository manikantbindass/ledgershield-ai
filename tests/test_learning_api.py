import numpy as np
import pytest
from fastapi.testclient import TestClient
from gymnasium.utils.env_checker import check_env
from backend.main import app
from ledgershield.core import Rejected
from ledgershield.learning import DQN, HealingEnv, load_policy


def test_gym_contract_and_seeded_episodes():
    env = HealingEnv(horizon=3)
    check_env(env, skip_render_check=True)
    runs = []
    for _ in range(2):
        obs, _ = env.reset(seed=123)
        result = []
        for action in (0, 1, 3):
            obs, reward, _, trunc, _ = env.step(action)
            result.append((obs.tolist(), reward, trunc))
        runs.append(result)
    assert runs[0] == runs[1]
    assert trunc
    with pytest.raises(Rejected):
        env.step(999)


def test_dqn_learning_checkpoint_and_fallback(tmp_path):
    model = DQN()
    before = model.w2.copy()
    obs = np.ones(12, dtype=np.float32)
    for _ in range(60):
        model.learn((obs, 2, 1., obs, False))
    assert not np.array_equal(before, model.w2)
    path = tmp_path / "dqn.json"
    model.save(path)
    assert np.array_equal(model.predict(obs), DQN.load(path).predict(obs))
    assert load_policy(tmp_path / "missing")[1] == "rule_fallback"


def test_api_stream_and_signed_transaction_lifecycle(monkeypatch):
    monkeypatch.setenv("LEDGERSHIELD_ADMIN_TOKEN", "test-admin-" + "a" * 40)
    with TestClient(app, headers={"Authorization": "Bearer test-admin-" + "a" * 40}) as client:
        assert client.get("/health").json()["integrity"]
        with client.websocket_connect("/ws/dashboard") as ws:
            assert ws.receive_json()["mode"] == "observe_only"
        tx = client.post("/simulation/transaction").json()
        assert client.post("/transactions", json=tx).json()["error"]["code"] == "duplicate_transaction"
        assert client.post("/transactions", json={"amount": 2}).status_code == 422
        client.post("/simulation/scenario", json={"node_id": "node_1", "behavior": "malicious"})
        state = client.post("/simulation/step").json()
        assert state["metrics"]["committed_transactions"] == 1
        assert any(a["verified"] for a in state["alerts"])
        assert client.get("/metrics").text.startswith("ledgershield_")
        assert client.post("/simulation/reset", json={"validator_count": 7, "node_count": 6}).status_code == 422
        assert client.post("/simulation/step", headers={"origin": "https://untrusted.example"}).status_code == 403
