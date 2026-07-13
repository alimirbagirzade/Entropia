#!/usr/bin/env bash
# =============================================================================
# Entropia — backup. Snapshots the two AUTHORITATIVE stateful stores into a
# timestamped local backup directory:
#   * PostgreSQL 16   (metadata store)          -> postgres.dump   [REQUIRED]
#   * MinIO / S3      (immutable artifact store) -> minio/          [OPTIONAL]
#
# Redis is intentionally NOT backed up: it holds a derivable queue + cache.
# In-flight work is recoverable from the durable outbox + INF-03 redelivery.
#
#   ./scripts/backup.sh                    # -> ./backups/<UTC-timestamp>/
#   BACKUP_DIR=/mnt/ext ./scripts/backup.sh
#   BACKUP_RETENTION=14 ./scripts/backup.sh
#
# Connection settings are read from ./.env (POSTGRES_* / OBJECT_STORAGE_*),
# falling back to the Docker-compose defaults. Host access uses localhost and
# the published ports (override with BACKUP_PGHOST / BACKUP_PGPORT /
# BACKUP_OBJECT_ENDPOINT).
#
# Exit code: 0 = Postgres captured (object storage may WARN-skip in the minimal
# Docker-free setup), 1 = a hard step failed.
#
# Full runbook, retention policy and disaster scenarios: docs/BACKUP_DR.md
# =============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

say()  { printf '%s\n' "$*"; }
pass() { say "  PASS  $*"; }
warn() { say "  WARN  $*"; }
fail() { say "  FAIL  $*" >&2; }

# Read a single KEY from .env, stripping inline comments/whitespace. Never
# executes the file (avoids sourcing arbitrary shell).
env_get() {
  [ -f "$ROOT/.env" ] || return 0
  sed -n "s/^$1=//p" "$ROOT/.env" | tail -1 | sed 's/[[:space:]]*#.*$//; s/^[[:space:]]*//; s/[[:space:]]*$//'
}

# ---- Postgres connection (host-facing) ----
PGHOST="${BACKUP_PGHOST:-localhost}"
PGPORT="${BACKUP_PGPORT:-5432}"
PGUSER="${POSTGRES_USER:-$(env_get POSTGRES_USER)}"; PGUSER="${PGUSER:-entropia}"
PGDATABASE="${POSTGRES_DB:-$(env_get POSTGRES_DB)}"; PGDATABASE="${PGDATABASE:-entropia}"
_pgpass="${POSTGRES_PASSWORD:-$(env_get POSTGRES_PASSWORD)}"; export PGPASSWORD="${_pgpass:-entropia}"

# ---- Object storage (host-facing endpoint) ----
_obj_raw="${OBJECT_STORAGE_ENDPOINT:-$(env_get OBJECT_STORAGE_ENDPOINT)}"; _obj_raw="${_obj_raw:-http://minio:9000}"
OBJ_ENDPOINT="${BACKUP_OBJECT_ENDPOINT:-$(printf '%s' "$_obj_raw" | sed 's#//minio:#//localhost:#')}"
OBJ_AK="${OBJECT_STORAGE_ACCESS_KEY:-$(env_get OBJECT_STORAGE_ACCESS_KEY)}"; OBJ_AK="${OBJ_AK:-entropia}"
OBJ_SK="${OBJECT_STORAGE_SECRET_KEY:-$(env_get OBJECT_STORAGE_SECRET_KEY)}"; OBJ_SK="${OBJ_SK:-entropia-secret}"
OBJ_BUCKET="${OBJECT_STORAGE_BUCKET:-$(env_get OBJECT_STORAGE_BUCKET)}"; OBJ_BUCKET="${OBJ_BUCKET:-entropia-artifacts}"

BACKUP_DIR="${BACKUP_DIR:-$ROOT/backups}"
BACKUP_RETENTION="${BACKUP_RETENTION:-7}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEST="$BACKUP_DIR/$STAMP"

command -v pg_dump >/dev/null 2>&1 || { fail "pg_dump not found — install the PostgreSQL client tools"; exit 1; }

say "== Entropia backup -> $DEST =="
mkdir -p "$DEST"

# ---- 1. PostgreSQL (REQUIRED) ----
say "== PostgreSQL ($PGDATABASE @ $PGHOST:$PGPORT) =="
if ! pg_dump -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -Fc -f "$DEST/postgres.dump" 2>"$DEST/postgres.dump.err"; then
  fail "pg_dump failed:"; sed 's/^/        /' "$DEST/postgres.dump.err" >&2
  rm -rf "$DEST"
  exit 1
fi
rm -f "$DEST/postgres.dump.err"
DUMP_BYTES=$(wc -c < "$DEST/postgres.dump" | tr -d ' ')
pass "postgres.dump written ($DUMP_BYTES bytes)"

ALEMBIC_HEAD=$(psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -tAc "select version_num from alembic_version" 2>/dev/null | head -1)
TABLE_COUNT=$(psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -tAc "select count(*) from information_schema.tables where table_schema='public'" 2>/dev/null | head -1)
pass "alembic head: ${ALEMBIC_HEAD:-unknown} · public tables: ${TABLE_COUNT:-unknown}"

# ---- 2. Object storage (OPTIONAL) ----
say "== Object storage ($OBJ_BUCKET @ $OBJ_ENDPOINT) =="
OBJ_INCLUDED=false
if ! curl -s --max-time 5 "$OBJ_ENDPOINT/minio/health/live" >/dev/null 2>&1; then
  warn "object storage unreachable — skipping artifact backup (OK for the minimal Docker-free setup)"
elif command -v mc >/dev/null 2>&1; then
  mkdir -p "$DEST/minio"
  mc alias set entropia_bak "$OBJ_ENDPOINT" "$OBJ_AK" "$OBJ_SK" >/dev/null 2>&1 || true
  if mc mirror --overwrite "entropia_bak/$OBJ_BUCKET" "$DEST/minio" >/dev/null 2>&1; then
    OBJ_INCLUDED=true; pass "mirrored bucket '$OBJ_BUCKET' via host mc"
  else
    warn "mc mirror failed — artifact backup skipped (Postgres dump still captured)"
  fi
elif command -v docker >/dev/null 2>&1; then
  mkdir -p "$DEST/minio"
  _ep="${OBJ_ENDPOINT/localhost/host.docker.internal}"
  if docker run --rm --add-host=host.docker.internal:host-gateway -v "$DEST/minio:/backup" \
      minio/mc:latest sh -c "mc alias set b '$_ep' '$OBJ_AK' '$OBJ_SK' >/dev/null && mc mirror --overwrite b/$OBJ_BUCKET /backup" >/dev/null 2>&1; then
    OBJ_INCLUDED=true; pass "mirrored bucket '$OBJ_BUCKET' via dockerized mc"
  else
    warn "dockerized mc mirror failed — artifact backup skipped (Postgres dump still captured)"
  fi
else
  warn "no 'mc' and no 'docker' — cannot back up object storage; skipping (Postgres dump still captured)"
fi
[ -d "$DEST/minio" ] && rmdir "$DEST/minio" 2>/dev/null || true  # drop empty dir on skip

# ---- 3. Manifest ----
GIT_COMMIT="$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)"
cat > "$DEST/MANIFEST.json" << JSON
{
  "created_at_utc": "$STAMP",
  "git_commit": "$GIT_COMMIT",
  "database": "$PGDATABASE",
  "alembic_head": "${ALEMBIC_HEAD:-unknown}",
  "public_table_count": ${TABLE_COUNT:-0},
  "postgres_dump_bytes": ${DUMP_BYTES:-0},
  "object_storage_included": $OBJ_INCLUDED,
  "object_bucket": "$OBJ_BUCKET"
}
JSON
pass "MANIFEST.json written"

# ---- 4. Retention prune (keep the newest BACKUP_RETENTION; bash 3.2 safe) ----
if [ "$BACKUP_RETENTION" -gt 0 ] 2>/dev/null; then
  _n=$(find "$BACKUP_DIR" -maxdepth 1 -type d -name '20*T*Z' | wc -l | tr -d ' ')
  if [ "$_n" -gt "$BACKUP_RETENTION" ]; then
    _drop=$(( _n - BACKUP_RETENTION ))
    find "$BACKUP_DIR" -maxdepth 1 -type d -name '20*T*Z' | sort | head -n "$_drop" | while IFS= read -r _d; do
      rm -rf "$_d"; warn "pruned old backup $(basename "$_d")"
    done
  fi
fi

say ""
say "BACKUP OK — $DEST"
say "  restore : ./scripts/restore.sh \"$DEST\" --yes"
say "  verify  : ./scripts/backup-verify.sh \"$DEST\""
exit 0
