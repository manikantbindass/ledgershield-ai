"""Exercise the actual container proxy/API/DB stack without printing credentials."""
import json
import os
from urllib.request import Request, urlopen


def call(path, payload=None):
    request = Request(
        "http://127.0.0.1:5173/api/v1" + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + os.environ["LEDGERSHIELD_ADMIN_TOKEN"]},
    )
    with urlopen(request, timeout=30) as response:
        return json.load(response)


if __name__ == "__main__":
    with urlopen("http://127.0.0.1:8000/ready", timeout=15) as response:
        assert json.load(response)["archive"] == "database"
    with urlopen("http://127.0.0.1:5173/healthz", timeout=15) as response:
        assert response.status == 200
    call("/simulation/transaction", {})
    call("/simulation/step", {})
    assert call("/blocks/1")["consensus"] == "verified"
    call("/healing/mode", {"mode": "approval_required"})
    call("/simulation/scenarios", {"node_id": "node_1", "behavior": "malicious"})
    call("/simulation/step", {})
    proposal = next(r for r in call("/healing/actions")["items"] if r["action"] == "quarantine")
    assert call("/healing/actions/" + proposal["id"] + "/approve", {})["status"] == "recovered"
    assert call("/archive/snapshot")["total"] > 0
    print("Container proxy, readiness, signed ledger, approved recovery and PostgreSQL archive verified.")
