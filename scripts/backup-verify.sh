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
# Exit codes — THREE distinct states, never collapsed (ADIM 34, RC §6.7 P6-6):
#   0  the backup restores into a coherent database
#   1  the backup does NOT restore — a verdict ON THE BACKUP
#   3  the backup could NOT BE VERIFIED — a verdict on the ENVIRONMENT (a
#      postgres client tool missing, or one of them not answering in time)
#
# Why 3 exists. Every external call below used to be unbounded, and the failures
# of the scratch-database plumbing were reported with the same exit 1 as a
# corrupt dump. MEASURED before the fix, both on the development host:
#   * a `dropdb` that never returns hung the whole script, forever;
#   * a `dropdb` that FAILS was swallowed by `|| true`, the next `createdb` then
#     failed on the leftover database, and a PERFECTLY SOUND backup was reported
#     with exit 1 — the code this file's own header documents as "it does not
#     restore". That false negative is what code 3 removes.
# The fix must never drift the other way: an unverifiable backup is NEVER
# reported as sound. 3 is non-zero, so CI/cron still fails on it. Uncertainty
# fails; it just no longer lies about WHAT failed.
#
# Run this after every backup and in CI/cron to catch silent corruption early.
# =============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# A guard that can hang is not a guard — see the file header.
. "$ROOT/scripts/lib/bounded.sh"

#: "the backup is broken". Reserved for verdicts about the DUMP.
EXIT_NOT_RESTORABLE=1
#: "we could not find out". Reserved for verdicts about the ENVIRONMENT.
EXIT_UNVERIFIED=3

# Bound for the postgres CONTROL-PLANE calls (dropdb/createdb/psql). MEASURED on
# the development host against local postgres: dropdb of an existing database
# 4.83s — the slowest of the three by an order of magnitude, and the very call
# the readiness report flagged — createdb 0.92s, a psql catalog query 0.13s.
# 60s is ~12x the slowest measured call, which absorbs a loaded CI box while
# still being a bound.
PG_TIMEOUT_SECONDS="${BACKUP_VERIFY_PG_TIMEOUT_SECONDS:-60}"
# pg_restore is the one call whose honest duration scales with the dump, so it
# gets its own, far looser bound: 30 minutes is well beyond any restore this
# project has produced and still finite, so a wedged restore ends as code 3
# instead of pinning a CI runner until the job timeout kills it with no verdict.
RESTORE_TIMEOUT_SECONDS="${BACKUP_VERIFY_RESTORE_TIMEOUT_SECONDS:-1800}"

say()  { printf '%s\n' "$*"; }
pass() { say "  PASS  $*"; }
warn() { say "  WARN  $*"; }
fail() { say "  FAIL  $*" >&2; }
# Environment failures get their own label, so a log reader sees the difference
# the exit code is making.
unverified() { say "  UNVERIFIED  $*" >&2; }

env_get() {
  [ -f "$ROOT/.env" ] || return 0
  sed -n "s/^$1=//p" "$ROOT/.env" | tail -1 | sed 's/[[:space:]]*#.*$//; s/^[[:space:]]*//; s/[[:space:]]*$//'
}

BACKUP_DIR="${BACKUP_DIR:-$ROOT/backups}"
SRC="${1:-}"
if [ -z "$SRC" ]; then
  SRC="$(find "$BACKUP_DIR" -maxdepth 1 -type d -name '20*T*Z' | sort | tail -1)"
  # No backup at all is not a statement about any backup's integrity.
  [ -n "$SRC" ] || { unverified "no backups found under $BACKUP_DIR — pass a backup dir explicitly"; exit "$EXIT_UNVERIFIED"; }
fi
# A backup directory with no dump in it IS a defective backup, not a broken host.
[ -f "$SRC/postgres.dump" ] || { fail "$SRC/postgres.dump not found — not a valid backup dir"; exit "$EXIT_NOT_RESTORABLE"; }

PGHOST="${BACKUP_PGHOST:-localhost}"
PGPORT="${BACKUP_PGPORT:-5432}"
PGUSER="${POSTGRES_USER:-$(env_get POSTGRES_USER)}"; PGUSER="${PGUSER:-entropia}"
_pgpass="${POSTGRES_PASSWORD:-$(env_get POSTGRES_PASSWORD)}"; export PGPASSWORD="${_pgpass:-entropia}"
VERIFY_DB="${VERIFY_DB:-entropia_restore_check}"

for t in pg_restore psql createdb dropdb; do
  command -v "$t" >/dev/null 2>&1 || { unverified "$t not found — install the PostgreSQL client tools"; exit "$EXIT_UNVERIFIED"; }
done

# Manifest expectations (best-effort; verification still runs without them).
EXP_HEAD="$(sed -n 's/.*"alembic_head": "\([^"]*\)".*/\1/p' "$SRC/MANIFEST.json" 2>/dev/null | head -1)"
EXP_TABLES="$(sed -n 's/.*"public_table_count": \([0-9]*\).*/\1/p' "$SRC/MANIFEST.json" 2>/dev/null | head -1)"

say "== Verifying backup $(basename "$SRC") into scratch DB '$VERIFY_DB' =="

drop_scratch_db() {
  bounded_run "$PG_TIMEOUT_SECONDS" dropdb -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" --if-exists "$VERIFY_DB" >/dev/null 2>&1
}

# EXIT trap: best-effort, bounded, and it must not change the verdict already
# reached. It may leave the scratch database behind; the pre-run drop below is
# what guarantees a clean slate, and THAT one is strict.
cleanup() { drop_scratch_db || true; }
trap cleanup EXIT

# Pre-run drop — strict. This is the call that used to fail silently and get
# mis-blamed on the backup one line later.
drop_rc=0
drop_scratch_db || drop_rc=$?
if [ "$drop_rc" -eq "$BOUNDED_TIMEOUT_RC" ]; then
  unverified "dropdb did not answer within ${PG_TIMEOUT_SECONDS}s — the scratch DB could not be reset, so this backup was NOT tested (this says nothing about the backup)"
  exit "$EXIT_UNVERIFIED"
elif [ "$drop_rc" -ne 0 ]; then
  unverified "dropdb --if-exists '$VERIFY_DB' failed (rc=$drop_rc) — the scratch DB could not be reset, so this backup was NOT tested (this says nothing about the backup)"
  exit "$EXIT_UNVERIFIED"
fi

create_rc=0
bounded_run "$PG_TIMEOUT_SECONDS" createdb -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" "$VERIFY_DB" || create_rc=$?
if [ "$create_rc" -eq "$BOUNDED_TIMEOUT_RC" ]; then
  unverified "createdb did not answer within ${PG_TIMEOUT_SECONDS}s — scratch DB '$VERIFY_DB' unavailable, backup NOT tested"
  exit "$EXIT_UNVERIFIED"
elif [ "$create_rc" -ne 0 ]; then
  unverified "could not create scratch DB '$VERIFY_DB' (rc=$create_rc) — backup NOT tested"
  exit "$EXIT_UNVERIFIED"
fi

rc=0
bounded_run "$RESTORE_TIMEOUT_SECONDS" pg_restore -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$VERIFY_DB" \
  --no-owner --no-privileges "$SRC/postgres.dump" 2>"$SRC/.verify.err" || rc=$?
if [ "$rc" -eq "$BOUNDED_TIMEOUT_RC" ]; then
  unverified "pg_restore did not finish within ${RESTORE_TIMEOUT_SECONDS}s — backup NOT tested (a partial restore proves nothing either way)"
  exit "$EXIT_UNVERIFIED"
fi
[ "$rc" -eq 0 ] || warn "pg_restore reported non-fatal warnings (see below if verification fails)"

# The two catalog reads. A timeout here means the assertions never ran, so their
# silence must not be read as "no tables" — that would fail a sound backup.
q_rc=0
GOT_HEAD=$(bounded_run "$PG_TIMEOUT_SECONDS" psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$VERIFY_DB" -tAc "select version_num from alembic_version" 2>/dev/null | head -1) || q_rc=$?
[ "$q_rc" -ne "$BOUNDED_TIMEOUT_RC" ] || { unverified "psql (alembic_version) did not answer within ${PG_TIMEOUT_SECONDS}s — backup NOT tested"; exit "$EXIT_UNVERIFIED"; }
q_rc=0
GOT_TABLES=$(bounded_run "$PG_TIMEOUT_SECONDS" psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$VERIFY_DB" -tAc "select count(*) from information_schema.tables where table_schema='public'" 2>/dev/null | head -1) || q_rc=$?
[ "$q_rc" -ne "$BOUNDED_TIMEOUT_RC" ] || { unverified "psql (table count) did not answer within ${PG_TIMEOUT_SECONDS}s — backup NOT tested"; exit "$EXIT_UNVERIFIED"; }

OK=0
if [ -n "$GOT_HEAD" ]; then pass "alembic_version present: $GOT_HEAD"; else fail "alembic_version missing — dump is not a coherent snapshot"; OK=1; fi
if [ -n "$EXP_HEAD" ] && [ "$GOT_HEAD" != "$EXP_HEAD" ]; then fail "alembic head mismatch: manifest=$EXP_HEAD restored=$GOT_HEAD"; OK=1; fi
if [ "${GOT_TABLES:-0}" -gt 0 ] 2>/dev/null; then pass "public tables restored: $GOT_TABLES"; else fail "no public tables restored"; OK=1; fi
if [ -n "$EXP_TABLES" ] && [ "$GOT_TABLES" != "$EXP_TABLES" ]; then fail "table-count mismatch: manifest=$EXP_TABLES restored=$GOT_TABLES"; OK=1; fi

if [ "$OK" -ne 0 ]; then
  fail "backup verification FAILED. pg_restore stderr:"
  sed 's/^/        /' "$SRC/.verify.err" >&2 2>/dev/null || true
  exit "$EXIT_NOT_RESTORABLE"
fi
rm -f "$SRC/.verify.err"

say ""
say "VERIFY OK — $(basename "$SRC") restores into a coherent database (head $GOT_HEAD, $GOT_TABLES tables)."
exit 0
