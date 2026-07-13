#!/usr/bin/env bash
# =============================================================================
# Entropia — restore. Recovers the two authoritative stores from a backup dir
# produced by scripts/backup.sh:
#   * PostgreSQL 16   <- postgres.dump   (pg_restore --clean --if-exists)
#   * MinIO / S3      <- minio/          (mc mirror --overwrite, additive)
#
# DESTRUCTIVE: the Postgres restore DROPs and recreates every object in the
# target database. Guarded — pass --yes or type the confirmation phrase.
#
#   ./scripts/restore.sh                       # restore the LATEST ./backups/*
#   ./scripts/restore.sh ./backups/<stamp>     # restore a specific backup
#   ./scripts/restore.sh ./backups/<stamp> --yes
#   RESTORE_DB=entropia_scratch ./scripts/restore.sh <dir> --yes   # dry target
#
# The object-storage mirror is ADDITIVE (overwrites matching keys, never
# deletes keys created after the backup). See docs/BACKUP_DR.md.
# =============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

say()  { printf '%s\n' "$*"; }
pass() { say "  PASS  $*"; }
warn() { say "  WARN  $*"; }
fail() { say "  FAIL  $*" >&2; }

env_get() {
  [ -f "$ROOT/.env" ] || return 0
  sed -n "s/^$1=//p" "$ROOT/.env" | tail -1 | sed 's/[[:space:]]*#.*$//; s/^[[:space:]]*//; s/[[:space:]]*$//'
}

BACKUP_DIR="${BACKUP_DIR:-$ROOT/backups}"

# ---- Resolve which backup to restore (arg, else latest) ----
SRC=""; ASSUME_YES=false
for arg in "$@"; do
  case "$arg" in
    --yes|-y) ASSUME_YES=true ;;
    *) SRC="$arg" ;;
  esac
done
if [ -z "$SRC" ]; then
  SRC="$(find "$BACKUP_DIR" -maxdepth 1 -type d -name '20*T*Z' | sort | tail -1)"
  [ -n "$SRC" ] || { fail "no backups found under $BACKUP_DIR — pass a backup dir explicitly"; exit 1; }
fi
[ -f "$SRC/postgres.dump" ] || { fail "$SRC/postgres.dump not found — not a valid backup dir"; exit 1; }

PGHOST="${BACKUP_PGHOST:-localhost}"
PGPORT="${BACKUP_PGPORT:-5432}"
PGUSER="${POSTGRES_USER:-$(env_get POSTGRES_USER)}"; PGUSER="${PGUSER:-entropia}"
PGDATABASE="${RESTORE_DB:-${POSTGRES_DB:-$(env_get POSTGRES_DB)}}"; PGDATABASE="${PGDATABASE:-entropia}"
_pgpass="${POSTGRES_PASSWORD:-$(env_get POSTGRES_PASSWORD)}"; export PGPASSWORD="${_pgpass:-entropia}"

command -v pg_restore >/dev/null 2>&1 || { fail "pg_restore not found — install the PostgreSQL client tools"; exit 1; }

HEAD="$(sed -n 's/.*"alembic_head": "\([^"]*\)".*/\1/p' "$SRC/MANIFEST.json" 2>/dev/null | head -1)"
say "== Entropia restore =="
say "  source : $SRC  (alembic head: ${HEAD:-unknown})"
say "  target : database '$PGDATABASE' @ $PGHOST:$PGPORT"
say ""
warn "This DROPs and recreates every object in '$PGDATABASE'. Existing data is lost."

if [ "$ASSUME_YES" != true ]; then
  printf 'Type "restore %s" to proceed: ' "$PGDATABASE"
  read -r reply
  [ "$reply" = "restore $PGDATABASE" ] || { fail "confirmation mismatch — aborted, nothing changed"; exit 1; }
fi

# ---- 1. PostgreSQL ----
# Ensure the target DB exists (createdb is a no-op-ish failure if it already does).
createdb -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" "$PGDATABASE" 2>/dev/null || true
say "== Restoring PostgreSQL =="
rc=0
pg_restore -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" \
  --clean --if-exists --no-owner --no-privileges "$SRC/postgres.dump" 2>"$SRC/.restore.err" || rc=$?
NEW_HEAD=$(psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -tAc "select version_num from alembic_version" 2>/dev/null | head -1)
if [ -n "$NEW_HEAD" ]; then
  [ "$rc" -eq 0 ] || warn "pg_restore reported non-fatal warnings (see $SRC/.restore.err)"
  pass "PostgreSQL restored — alembic head now: $NEW_HEAD"
  rm -f "$SRC/.restore.err"
else
  fail "restore did not produce a coherent database (no alembic_version):"
  sed 's/^/        /' "$SRC/.restore.err" >&2
  exit 1
fi

# ---- 2. Object storage (if the backup captured it) ----
if [ -d "$SRC/minio" ]; then
  _obj_raw="${OBJECT_STORAGE_ENDPOINT:-$(env_get OBJECT_STORAGE_ENDPOINT)}"; _obj_raw="${_obj_raw:-http://minio:9000}"
  OBJ_ENDPOINT="${BACKUP_OBJECT_ENDPOINT:-$(printf '%s' "$_obj_raw" | sed 's#//minio:#//localhost:#')}"
  OBJ_AK="${OBJECT_STORAGE_ACCESS_KEY:-$(env_get OBJECT_STORAGE_ACCESS_KEY)}"; OBJ_AK="${OBJ_AK:-entropia}"
  OBJ_SK="${OBJECT_STORAGE_SECRET_KEY:-$(env_get OBJECT_STORAGE_SECRET_KEY)}"; OBJ_SK="${OBJ_SK:-entropia-secret}"
  OBJ_BUCKET="${OBJECT_STORAGE_BUCKET:-$(env_get OBJECT_STORAGE_BUCKET)}"; OBJ_BUCKET="${OBJ_BUCKET:-entropia-artifacts}"
  say "== Restoring object storage ($OBJ_BUCKET @ $OBJ_ENDPOINT) =="
  if ! curl -s --max-time 5 "$OBJ_ENDPOINT/minio/health/live" >/dev/null 2>&1; then
    warn "object storage unreachable — artifacts NOT restored (start MinIO and re-run to restore them)"
  elif command -v mc >/dev/null 2>&1; then
    mc alias set entropia_bak "$OBJ_ENDPOINT" "$OBJ_AK" "$OBJ_SK" >/dev/null 2>&1 || true
    mc mb --ignore-existing "entropia_bak/$OBJ_BUCKET" >/dev/null 2>&1 || true
    if mc mirror --overwrite "$SRC/minio" "entropia_bak/$OBJ_BUCKET" >/dev/null 2>&1; then
      pass "object storage restored via host mc"
    else
      warn "mc mirror (restore) failed — check MinIO credentials/endpoint"
    fi
  elif command -v docker >/dev/null 2>&1; then
    _ep="${OBJ_ENDPOINT/localhost/host.docker.internal}"
    if docker run --rm --add-host=host.docker.internal:host-gateway -v "$SRC/minio:/backup" \
        minio/mc:latest sh -c "mc alias set b '$_ep' '$OBJ_AK' '$OBJ_SK' >/dev/null && mc mb --ignore-existing b/$OBJ_BUCKET >/dev/null && mc mirror --overwrite /backup b/$OBJ_BUCKET" >/dev/null 2>&1; then
      pass "object storage restored via dockerized mc"
    else
      warn "dockerized mc mirror (restore) failed"
    fi
  else
    warn "no 'mc' and no 'docker' — object storage not restored"
  fi
fi

say ""
say "RESTORE OK — '$PGDATABASE' recovered from $(basename "$SRC")."
exit 0
