import os

from alembic import context
from sqlalchemy import create_engine

from backend.persistence import metadata

url = os.environ.get("DATABASE_URL", "sqlite:///artifacts/ledger.db")

if context.is_offline_mode():
    context.configure(url=url, target_metadata=metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(url)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
