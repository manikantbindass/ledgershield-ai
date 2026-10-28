"""Archive public state after successful changes, never credentials."""

import os

from ledgershield.core import digest

from .persistence import RecordStore


def open_store():
    url = os.getenv("DATABASE_URL")
    if not url:
        return None
    store = RecordStore(url)
    try:
        store.ready()
    except Exception:
        store.close()
        raise RuntimeError("Database archive is unavailable or migrations are missing") from None
    return store


def archive(app):
    store = app.state.store
    if store is None:
        return
    svc = app.state.service
    items = [("snapshot", svc.instance_id, svc.state())]
    items.extend(("event", event["id"], dict(event)) for event in svc.events)
    items.extend(
        ("healing", f"{svc.instance_id}:{row['id']}", dict(row)) for row in svc.recovery.audit
    )
    items.extend(("experiment", row["id"], dict(row)) for row in app.state.experiments.values())
    items.extend(
        ("block", f"{svc.instance_id}:{block.index}", block.to_dict())
        for block in svc.network.ledger.chain
    )
    items.extend(
        ("transaction", f"{svc.instance_id}:{key}", dict(row))
        for key, row in svc.network.transaction_records.items()
    )
    items.extend(
        ("alert", f"{svc.instance_id}:{row['id']}", dict(row)) for row in svc.detector.alerts
    )
    items.extend(
        ("trust", f"{svc.instance_id}:{row['node_id']}:{row['evidence_id']}", dict(row))
        for row in svc.trust.audit
    )
    items.extend(
        ("scenario", f"{svc.instance_id}:{row['id']}", dict(row)) for row in svc.scenario_runs.runs
    )
    cache = getattr(app.state, "archive_cache", {})
    changes = [(kind, key, payload, digest(payload)) for kind, key, payload in items]
    fingerprints = {(kind, key): fingerprint for kind, key, payload, fingerprint in changes}
    changes = [row for row in changes if cache.get((row[0], row[1])) != row[3]]
    store.put_many((kind, key, payload) for kind, key, payload, fingerprint in changes)
    app.state.archive_cache = fingerprints
