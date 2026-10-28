"""Verify real Prometheus scraping and provisioned Grafana over HTTP in CI."""
import base64
import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def wait_json(url, headers=None, predicate=None):
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        try:
            with urlopen(Request(url, headers=headers or {}), timeout=5) as response:
                value = json.load(response)
            if predicate is None or predicate(value):
                return value
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
            pass  # Startup retries are bounded; absence is a failing assertion below.
        time.sleep(1)
    raise AssertionError("Monitoring did not reach its required readiness state")


if __name__ == "__main__":
    wait_json("http://127.0.0.1:3001/api/health", predicate=lambda row: row["database"] == "ok")
    query = urlencode({"query": "ledgershield_height"})
    wait_json("http://127.0.0.1:9090/api/v1/query?" + query,
              predicate=lambda row: row["status"] == "success" and bool(row["data"]["result"]))
    credentials = base64.b64encode(("ledger:" + os.environ["GRAFANA_ADMIN_PASSWORD"]).encode()).decode()
    dashboard = wait_json("http://127.0.0.1:3001/api/dashboards/uid/ledgershield-network",
                          headers={"Authorization": "Basic " + credentials})
    assert len(dashboard["dashboard"]["panels"]) == 4
    assert dashboard["dashboard"]["uid"] == "ledgershield-network"
    print("Prometheus scraped actual simulator metrics and Grafana provisioned all four research panels.")
