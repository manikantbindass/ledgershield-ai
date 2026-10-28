"""Archive public state after successful changes, never credentials."""

import os

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
    store.put_many(items)
