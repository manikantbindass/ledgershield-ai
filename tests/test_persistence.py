import os
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import StatementError

from backend.main import app
from backend.persistence import RecordStore


def migrate(url):
    env = {**os.environ, "DATABASE_URL": url}
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        env=env,
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )


@pytest.fixture
def database(tmp_path):
    url = os.environ.get("TEST_DATABASE_URL", "sqlite:///" + (tmp_path / "research.db").as_posix())
    migrate(url)
    return url


def test_record_transactions_rollback_and_reopen(database):
    store = RecordStore(database)
    assert store.ready()
    store.put_many([("test", "retained", {"value": 1})])
    with pytest.raises(StatementError):
        store.put_many(
            [("test", "rolled-back", {"value": 2}), ("test", "invalid", {"bad": object()})]
        )
    assert not any(r.get("value") == 2 for r in store.list("test"))
    store.close()
    reopened = RecordStore(database)
    assert {"value": 1} in reopened.list("test")
    reopened.close()


def test_api_persists_experiments_public_snapshots_and_audits(database, monkeypatch):
    token = "persistence-test-" + "x" * 40
    monkeypatch.setenv("DATABASE_URL", database)
    monkeypatch.setenv("LEDGERSHIELD_ADMIN_TOKEN", token)
    headers = {"Authorization": "Bearer " + token}
    with TestClient(app) as client:
        assert client.get("/ready").json()["archive"] == "database"
        client.post("/api/v1/simulation/transaction", headers=headers)
        client.post("/api/v1/simulation/step", headers=headers)
        experiment = client.post(
            "/api/v1/policies/evaluate", headers=headers, json={"episodes": 1, "horizon": 1}
        ).json()
        record_id = experiment["id"]
        snapshots = client.get("/api/v1/archive/snapshot").json()
        assert snapshots["storage"] == "database_archive"
        assert any(r["metrics"]["committed_transactions"] == 1 for r in snapshots["items"])
        assert token not in str(snapshots)
        assert "private_key" not in str(snapshots)
        assert client.get("/api/v1/archive/event").json()["total"] > 0
    with TestClient(app) as client:
        assert client.get("/api/v1/experiments/" + record_id).status_code == 200
        assert client.get("/api/v1/network/overview").json()["metrics"]["height"] == 0
        assert not client.get("/api/v1/network/overview").json()["running"]


def test_readiness_and_write_failures_are_visible(database, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", database)
    monkeypatch.setenv("LEDGERSHIELD_ADMIN_TOKEN", "archive-test-" + "x" * 40)
    with TestClient(app) as client:
        original = app.state.store.put_many

        def broken(_):
            raise RuntimeError("secret-db-password")

        monkeypatch.setattr(app.state.store, "put_many", broken)
        response = client.post(
            "/api/v1/simulation/step", headers={"Authorization": "Bearer archive-test-" + "x" * 40}
        )
        assert (
            response.status_code == 503
            and response.json()["error"]["code"] == "archive_unavailable"
        )
        assert "secret-db-password" not in response.text
        assert not app.state.service.running
        monkeypatch.setattr(app.state.store, "put_many", original)
        monkeypatch.setattr(
            app.state.store, "ready", lambda: (_ for _ in ()).throw(RuntimeError("secret"))
        )
        assert client.get("/ready").status_code == 503


def test_missing_migrations_fail_at_startup(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///" + (tmp_path / "unmigrated.db").as_posix())
    with pytest.raises(RuntimeError, match="migrations are missing"):
        with TestClient(app):
            pass
