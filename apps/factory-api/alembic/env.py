from __future__ import annotations

import os
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from shared_contracts.db import Base
from sqlalchemy import engine_from_config, pool
from task_engine import models as task_models  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
target_metadata = Base.metadata
_CHECKPOINTER_TABLES = {
    "checkpoint_blobs",
    "checkpoint_migrations",
    "checkpoint_writes",
    "checkpoints",
}


def include_object(obj, name, object_type, reflected, compare_to):
    """LangGraph owns its checkpoint schema; factory migrations must leave it alone."""
    if object_type == "table":
        table_name = name
    else:
        table_name = getattr(getattr(obj, "table", None), "name", None)
    return table_name not in _CHECKPOINTER_TABLES


url = os.getenv("DATABASE_URL", config.get_main_option("sqlalchemy.url"))
config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
if url.startswith("sqlite:///"):
    Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)


def run_migrations_offline() -> None:
    context.configure(
        url=url,
        target_metadata=target_metadata,
        include_object=include_object,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


run_migrations_offline() if context.is_offline_mode() else run_migrations_online()
