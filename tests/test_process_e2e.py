"""Real uvicorn process and HTTP/WebSocket transport, not TestClient."""

import asyncio
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import requests
from websockets.asyncio.client import connect


def test_real_application_transaction_fault_approval_and_stream(tmp_path):
    root = Path(__file__).resolve().parents[1]
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    token = "process-e2e-" + "x" * 40
    env = {**os.environ, "LEDGERSHIELD_ADMIN_TOKEN": token, "RECOVERY_MODE": "observe_only"}
    env.pop("DATABASE_URL", None)
    log = tmp_path / "server.log"
    with log.open("w", encoding="utf-8") as output:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "backend.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--no-access-log",
            ],
            cwd=root,
            env=env,
            stdout=output,
            stderr=output,
        )
        try:
            base = f"http://127.0.0.1:{port}"
            ready = False
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise AssertionError("API process exited during startup; inspect test log")
                try:
                    ready = requests.get(base + "/ready", timeout=(2, 5)).status_code == 200
                except (requests.ConnectionError, requests.Timeout):
                    ready = False
                if ready:
                    break
                time.sleep(0.1)
            assert ready

            def post(path, body=None):
                response = requests.post(
                    base + "/api/v1" + path,
                    headers={"Authorization": "Bearer " + token},
                    json=body or {},
                    timeout=20,
                )
                assert response.status_code < 300, (path, response.status_code, response.text)
                return response.json()

            post("/simulation/reset")
            tx = post("/simulation/transaction")
            post("/simulation/step")
            block = requests.get(base + "/api/v1/blocks/1", timeout=10).json()
            assert block["consensus"] == "verified" and block["state_integrity"]
            assert block["block"]["transactions"][0] == tx
            post("/healing/mode", {"mode": "approval_required"})
            post("/simulation/scenarios", {"node_id": "node_1", "behavior": "malicious"})
            post("/simulation/step")
            alerts = requests.get(base + "/api/v1/alerts", timeout=10).json()["items"]
            assert any(a["verified"] for a in alerts)
            actions = requests.get(base + "/api/v1/healing/actions", timeout=10).json()["items"]
            proposal = next(a for a in actions if a["action"] == "quarantine")
            result = post(f"/healing/actions/{proposal['id']}/approve")
            assert result["status"] == "recovered"

            async def stream():
                async with connect(f"ws://127.0.0.1:{port}/api/v1/ws") as ws:
                    return json.loads(await asyncio.wait_for(ws.recv(), timeout=10))

            snapshot = asyncio.run(stream())["data"]
            assert snapshot["metrics"]["recovery_successes"] == 1
            assert next(n for n in snapshot["nodes"] if n["id"] == "node_1")["quarantined"]
            assert snapshot["metrics"]["committed_transactions"] == 1
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
