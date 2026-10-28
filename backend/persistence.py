"""Transactional public-record archive. Simulator replicas remain volatile.

One process owns the simulator. This store preserves completed experiments,
audit events, and public snapshots; it never stores private keys or tokens and
does not claim to resume a live consensus machine after process restart.
"""

import builtins
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    MetaData,
    String,
    Table,
    create_engine,
    func,
    select,
    text,
)
from sqlalchemy.engine import Engine

metadata = MetaData()
records = Table(
    "research_records",
    metadata,
    Column("kind", String(32), primary_key=True),
    Column("record_id", String(160), primary_key=True),
    Column("payload", JSON, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)


class RecordStore:
    def __init__(self, url: str) -> None:
        self.engine: Engine = create_engine(
            url,
            pool_pre_ping=True,
            connect_args={"check_same_thread": False} if url.startswith("sqlite") else {},
        )

    def ready(self) -> bool:
        with self.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            connection.execute(select(records.c.record_id).limit(1))
        return True

    def put_many(self, items: Iterable[tuple[str, str, dict[str, Any]]]) -> None:
        """All records in one transaction; failures propagate and roll back."""
        with self.engine.begin() as connection:
            for kind, record_id, payload in items:
                query = (records.c.kind == kind) & (records.c.record_id == record_id)
                existing = connection.execute(select(records.c.record_id).where(query)).first()
                if existing:
                    connection.execute(records.update().where(query).values(payload=payload))
                else:
                    connection.execute(
                        records.insert().values(
                            kind=kind,
                            record_id=record_id,
                            payload=payload,
                            created_at=datetime.now(timezone.utc),
                        )
                    )

    def list(self, kind: str, limit: int = 100) -> list[dict[str, Any]]:
        with self.engine.connect() as connection:
            result = connection.execute(
                select(records.c.payload)
                .where(records.c.kind == kind)
                .order_by(records.c.created_at.desc(), records.c.record_id)
                .limit(limit)
            )
            return [dict(row[0]) for row in result]

    def close(self) -> None:
        self.engine.dispose()

    def page(self, kind: str, offset: int, limit: int) -> tuple[builtins.list[dict[str, Any]], int]:
        with self.engine.connect() as connection:
            total = int(
                connection.execute(
                    select(func.count()).select_from(records).where(records.c.kind == kind)
                ).scalar_one()
            )
            result = connection.execute(
                select(records.c.payload)
                .where(records.c.kind == kind)
                .order_by(records.c.created_at.desc(), records.c.record_id)
                .offset(offset)
                .limit(limit)
            )
            return [dict(row[0]) for row in result], total
