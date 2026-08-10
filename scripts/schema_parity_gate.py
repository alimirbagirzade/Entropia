"""Gate: the ORM models and the migrations must describe the SAME indexes.

Why this exists
---------------
``alembic check`` reported 40 index-axis deviations for the whole life of the
project and **no workflow ran it** (RC §6.7 P4-1), so the deviation was unowned.
Two of the tables also disagreed structurally: ``agent_event.seq`` carried an
extra non-unique index on the migration path that ``create_all`` never built
(P4-2). Both are closed; this gate is what keeps them closed.

What it asserts
---------------
1. **Install-path parity.** A database built by ``alembic upgrade head`` and a
   database built by ``Base.metadata.create_all`` must carry the byte-identical
   set of indexes: same names, same columns, same uniqueness. This is the
   assertion ``alembic check`` cannot make, because alembic *skips* expression
   indexes that carry an operator class (the four ``audit_events`` trigram /
   ``varchar_pattern_ops`` indexes) and silently assumes them equal.
2. **Model/migration index parity.** ``compare_metadata`` against the
   alembic-built database must emit ZERO index- or constraint-axis operations.

What it does NOT assert
-----------------------
**The overall ``alembic check`` exit code.** That command is still non-zero, for
a deviation class this gate deliberately leaves alone: 60 columns across 40
tables where the database carries a server default that the model declares only
Python-side (``default=`` without ``server_default=``). Adding those changes what
``create_all`` builds, so it is a separate decision and a separate change. The
count is asserted below so it cannot grow unnoticed, but it is NOT zero and this
gate does not pretend it is.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from urllib.parse import urlsplit, urlunsplit

import asyncpg
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from entropia.config import get_settings
from entropia.infrastructure.postgres import models as postgres_models
from entropia.infrastructure.postgres.base import Base

# Importing the models package is what registers every table on ``Base.metadata``.
# The name is referenced below so the import cannot be read as a dead one.
MODEL_PACKAGE = postgres_models.__name__

# Operation names that carry the index/constraint axis this gate owns.
INDEX_AXIS_OPS = frozenset({"add_index", "remove_index", "add_constraint", "remove_constraint"})

# Deviations knowingly left to a separate change (see module docstring). The gate
# fails if this grows: an unfixed problem may stay unfixed, but it may not spread.
EXPECTED_SERVER_DEFAULT_DEVIATIONS = 60

INDEX_SHAPE_SQL = """
SELECT t.relname AS tbl, i.relname AS idx, ix.indisunique AS uniq,
       pg_get_indexdef(i.oid) AS full_def
FROM pg_index ix
JOIN pg_class i ON i.oid = ix.indexrelid
JOIN pg_class t ON t.oid = ix.indrelid
JOIN pg_namespace n ON n.oid = t.relnamespace
WHERE n.nspname = 'public' AND t.relkind = 'r' AND t.relname <> 'alembic_version'
"""


def _swap_database(url: str, name: str) -> str:
    parts = urlsplit(url)
    return urlunsplit(parts._replace(path=f"/{name}"))


def _asyncpg_url(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://")


async def _index_shape(url: str) -> dict[tuple[str, str], tuple[bool, str]]:
    conn = await asyncpg.connect(_asyncpg_url(url))
    try:
        rows = await conn.fetch(INDEX_SHAPE_SQL)
    finally:
        await conn.close()
    # Compare the definition WITHOUT the index name, so a rename shows up as a
    # name difference rather than as two unrelated shapes.
    return {(r["tbl"], r["idx"]): (r["uniq"], r["full_def"].split(" ON ", 1)[1]) for r in rows}


async def _build_create_all(url: str) -> None:
    engine = create_async_engine(url)
    try:
        async with engine.begin() as conn:
            await conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS pg_trgm")
            await conn.run_sync(Base.metadata.create_all)
    finally:
        await engine.dispose()


async def _reset_probe_database(admin_url: str, probe_name: str) -> None:
    conn = await asyncpg.connect(_asyncpg_url(admin_url))
    try:
        await conn.execute(f'DROP DATABASE IF EXISTS "{probe_name}" WITH (FORCE)')
        await conn.execute(f'CREATE DATABASE "{probe_name}"')
    finally:
        await conn.close()


def _autogenerate_diff(sync_conn: Connection) -> list:
    context = MigrationContext.configure(
        sync_conn,
        opts={"compare_type": True, "compare_server_default": True},
    )
    return compare_metadata(context, Base.metadata)


async def _model_vs_migration_ops(url: str) -> list:
    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            return await conn.run_sync(_autogenerate_diff)
    finally:
        await engine.dispose()


def _op_name(op: object) -> str:
    if isinstance(op, tuple) and op and isinstance(op[0], str):
        return op[0]
    return getattr(op, "__visit_name__", type(op).__name__)


def _verdict(ok: bool, *, ok_text: str = "PASS", bad_text: str = "FAIL") -> str:
    if ok:
        return ok_text
    return bad_text


def _flatten(ops: list) -> list:
    """compare_metadata groups per-table modifications into nested lists."""
    out: list = []
    for op in ops:
        if isinstance(op, list):
            out.extend(op)
        else:
            out.append(op)
    return out


async def run(probe_suffix: str) -> int:
    if not Base.metadata.tables:
        raise RuntimeError(f"no tables registered on Base.metadata — {MODEL_PACKAGE} did not load")

    migrated_url = get_settings().database_url
    probe_name = urlsplit(migrated_url).path.lstrip("/") + probe_suffix
    admin_url = _swap_database(migrated_url, "postgres")
    probe_url = _swap_database(migrated_url, probe_name)

    print(f"migrated database : {urlsplit(migrated_url).path.lstrip('/')}")
    print(f"create_all probe  : {probe_name}")

    await _reset_probe_database(admin_url, probe_name)
    await _build_create_all(probe_url)

    migrated = await _index_shape(migrated_url)
    probe = await _index_shape(probe_url)

    only_migrated = sorted(set(migrated) - set(probe))
    only_probe = sorted(set(probe) - set(migrated))
    differing = sorted(k for k in set(migrated) & set(probe) if migrated[k] != probe[k])

    print(f"\n[1] install-path index parity — {len(migrated)} vs {len(probe)} indexes")
    for tbl, idx in only_migrated:
        print(f"    MIGRATION-ONLY  {tbl}.{idx}  unique={migrated[(tbl, idx)][0]}")
    for tbl, idx in only_probe:
        print(f"    CREATE_ALL-ONLY {tbl}.{idx}  unique={probe[(tbl, idx)][0]}")
    for key in differing:
        print(f"    DIFFERS         {key[0]}.{key[1]}  {migrated[key]} != {probe[key]}")
    parity_ok = not (only_migrated or only_probe or differing)
    print(f"    -> {_verdict(parity_ok)}")

    ops = _flatten(await _model_vs_migration_ops(migrated_url))
    index_ops = [op for op in ops if _op_name(op) in INDEX_AXIS_OPS]
    default_ops = [op for op in ops if _op_name(op) == "modify_default"]
    other_ops = [op for op in ops if _op_name(op) not in INDEX_AXIS_OPS | {"modify_default"}]

    print(f"\n[2] model/migration index axis — {len(index_ops)} operation(s)")
    for op in index_ops:
        print(f"    {op}")
    index_axis_ok = not index_ops
    print(f"    -> {_verdict(index_axis_ok)}")

    print(f"\n[3] NOT owned by this gate — server-default deviations: {len(default_ops)}")
    print(f"    expected {EXPECTED_SERVER_DEFAULT_DEVIATIONS} (see module docstring);")
    print("    `alembic check` stays non-zero because of these. Not asserted clean.")
    budget_ok = len(default_ops) <= EXPECTED_SERVER_DEFAULT_DEVIATIONS
    print(f"    -> {_verdict(budget_ok, ok_text='PASS (no growth)', bad_text='FAIL (grew)')}")

    unexpected_ok = not other_ops
    print(f"\n[4] no other schema drift — {len(other_ops)} operation(s)")
    for op in other_ops:
        print(f"    {op}")
    print(f"    -> {_verdict(unexpected_ok)}")

    ok = parity_ok and index_axis_ok and budget_ok and unexpected_ok
    print(f"\nVERDICT: {_verdict(ok)}")
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--probe-suffix",
        default="_create_all_probe",
        help="suffix for the scratch database built via create_all",
    )
    args = parser.parse_args()
    return asyncio.run(run(args.probe_suffix))


if __name__ == "__main__":
    sys.exit(main())
