#!/usr/bin/env bash
# =============================================================================
# Entropia — backup verification. Proves a backup is actually restorable:
# restores its postgres.dump into a THROWAWAY scratch database, asserts the
# result is a coherent snapshot (alembic_version present + table count matches
# the manifest), then drops the scratch database. Touches nothing else.
#
#   ./scripts/backup-verify.sh                    # verify the LATEST ./backups/*
#   ./scripts/backup-verify.sh ./backups/<stamp>  # verify a specific backup
#   VERIFY_DB=entropia_restore_check ./scripts/backup-verify.sh
#
# Exit code: 0 = backup restores into a coherent database, 1 = it does not.
# Run this after every backup and in CI/cron to catch silent corruption early.
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
SRC="${1:-}"
if [ -z "$SRC" ]; then
  SRC="$(find "$BACKUP_DIR" -maxdepth 1 -type d -name '20*T*Z' | sort | tail -1)"
  [ -n "$SRC" ] || { fail "no backups found under $BACKUP_DIR — pass a backup dir explicitly"; exit 1; }
fi
[ -f "$SRC/postgres.dump" ] || { fail "$SRC/postgres.dump not found — not a valid backup dir"; exit 1; }

PGHOST="${BACKUP_PGHOST:-localhost}"
PGPORT="${BACKUP_PGPORT:-5432}"
PGUSER="${POSTGRES_USER:-$(env_get POSTGRES_USER)}"; PGUSER="${PGUSER:-entropia}"
_pgpass="${POSTGRES_PASSWORD:-$(env_get POSTGRES_PASSWORD)}"; export PGPASSWORD="${_pgpass:-entropia}"
VERIFY_DB="${VERIFY_DB:-entropia_restore_check}"

for t in pg_restore psql createdb dropdb; do
  command -v "$t" >/dev/null 2>&1 || { fail "$t not found — install the PostgreSQL client tools"; exit 1; }
done

# Manifest expectations (best-effort; verification still runs without them).
EXP_HEAD="$(sed -n 's/.*"alembic_head": "\([^"]*\)".*/\1/p' "$SRC/MANIFEST.json" 2>/dev/null | head -1)"
EXP_TABLES="$(sed -n 's/.*"public_table_count": \([0-9]*\).*/\1/p' "$SRC/MANIFEST.json" 2>/dev/null | head -1)"

say "== Verifying backup $(basename "$SRC") into scratch DB '$VERIFY_DB' =="

cleanup() { dropdb -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" --if-exists "$VERIFY_DB" >/dev/null 2>&1 || true; }
trap cleanup EXIT

cleanup  # drop any leftover from a previous aborted run
createdb -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" "$VERIFY_DB" || { fail "could not create scratch DB '$VERIFY_DB'"; exit 1; }

rc=0
pg_restore -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$VERIFY_DB" \
  --no-owner --no-privileges "$SRC/postgres.dump" 2>"$SRC/.verify.err" || rc=$?
[ "$rc" -eq 0 ] || warn "pg_restore reported non-fatal warnings (see below if verification fails)"

GOT_HEAD=$(psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$VERIFY_DB" -tAc "select version_num from alembic_version" 2>/dev/null | head -1)
GOT_TABLES=$(psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$VERIFY_DB" -tAc "select count(*) from information_schema.tables where table_schema='public'" 2>/dev/null | head -1)

OK=0
if [ -n "$GOT_HEAD" ]; then pass "alembic_version present: $GOT_HEAD"; else fail "alembic_version missing — dump is not a coherent snapshot"; OK=1; fi
if [ -n "$EXP_HEAD" ] && [ "$GOT_HEAD" != "$EXP_HEAD" ]; then fail "alembic head mismatch: manifest=$EXP_HEAD restored=$GOT_HEAD"; OK=1; fi
if [ "${GOT_TABLES:-0}" -gt 0 ] 2>/dev/null; then pass "public tables restored: $GOT_TABLES"; else fail "no public tables restored"; OK=1; fi
if [ -n "$EXP_TABLES" ] && [ "$GOT_TABLES" != "$EXP_TABLES" ]; then fail "table-count mismatch: manifest=$EXP_TABLES restored=$GOT_TABLES"; OK=1; fi

if [ "$OK" -ne 0 ]; then
  fail "backup verification FAILED. pg_restore stderr:"
  sed 's/^/        /' "$SRC/.verify.err" >&2 2>/dev/null || true
  exit 1
fi
rm -f "$SRC/.verify.err"

say ""
say "VERIFY OK — $(basename "$SRC") restores into a coherent database (head $GOT_HEAD, $GOT_TABLES tables)."
exit 0
