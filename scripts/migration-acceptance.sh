#!/usr/bin/env bash
# =============================================================================
# Entropia — MIGRATION + PROVISIONING acceptance (ADIM 22).
#
# Proves the schema half of the real installation chain against a REAL
# PostgreSQL, using the REAL install path (`alembic upgrade`), never
# `metadata.create_all`. It is deliberately Docker-free and fast (~1 min) so it
# can gate every PR; the heavy Docker flows live in scripts/e2e-acceptance.sh.
#
#   scripts/migration-acceptance.sh
#   MIGRATION_ACCEPTANCE_DB=my_scratch scripts/migration-acceptance.sh
#
# What it asserts (each an ADIM 22 mandated step):
#   [1] the revision graph has exactly ONE head
#   [2] fresh install: empty database -> `alembic upgrade head` -> head stamped
#   [3] migration<->model COLUMN parity (migrated schema == Base.metadata)
#   [4] migration-provisioned rows land (the `alpha-agent` agent_runtime row
#       from 0016 exists on the real install path)
#   [5] representative LEGACY revisions -> head with pre-existing rows preserved
#   [6] the LATEST revision down/up round-trips and preserves data
#   [7] provisioning (`python -m entropia.apps.seed`) is REPEAT-idempotent
#   [8] provisioning is CONCURRENT-idempotent: parallel runs all exit 0 and
#       existing state is never reset or duplicated
#
# Safety: every step runs inside a scratch database whose name must differ from
# the configured POSTGRES_DB. A hard guard refuses to drop anything else.
#
# Exit code: 0 = every step passed, 1 = a step failed, 2 = the environment is
# not usable (no psql / no reachable PostgreSQL).
# =============================================================================
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"

BOLD=$'\033[1m'; DIM=$'\033[2m'; RED=$'\033[31m'; GRN=$'\033[32m'; CYA=$'\033[36m'; RST=$'\033[0m'
PASS_N=0; FAIL_N=0
step() { printf '\n%s— %s%s\n' "$CYA" "$*" "$RST"; }
ok()   { PASS_N=$((PASS_N+1)); printf '  %sPASS%s  %s\n' "$GRN" "$RST" "$*"; }
bad()  { FAIL_N=$((FAIL_N+1)); printf '  %sFAIL%s  %s\n' "$RED" "$RST" "$*"; }
info() { printf '  %s%s%s\n' "$DIM" "$*" "$RST"; }

# Read a single KEY from .env without executing it (same idiom as backup.sh).
env_get() {
  [ -f "$ROOT/.env" ] || return 0
  sed -n "s/^$1=//p" "$ROOT/.env" | tail -1 | sed 's/[[:space:]]*#.*$//; s/^[[:space:]]*//; s/[[:space:]]*$//'
}

PGHOST="${ACCEPTANCE_PGHOST:-localhost}"
PGPORT="${ACCEPTANCE_PGPORT:-5432}"
PGUSER="${POSTGRES_USER:-$(env_get POSTGRES_USER)}"; PGUSER="${PGUSER:-entropia}"
_pgpass="${POSTGRES_PASSWORD:-$(env_get POSTGRES_PASSWORD)}"; export PGPASSWORD="${_pgpass:-entropia}"
LIVE_DB="${POSTGRES_DB:-$(env_get POSTGRES_DB)}"; LIVE_DB="${LIVE_DB:-entropia}"
SCRATCH_DB="${MIGRATION_ACCEPTANCE_DB:-entropia_migration_acceptance}"

# ---- guards ------------------------------------------------------------------
for t in psql createdb dropdb; do
  command -v "$t" >/dev/null 2>&1 || { echo "FATAL: $t not found — install the PostgreSQL client tools." >&2; exit 2; }
done
if [ "$SCRATCH_DB" = "$LIVE_DB" ]; then
  echo "FATAL: MIGRATION_ACCEPTANCE_DB ('$SCRATCH_DB') must differ from the live database ('$LIVE_DB')." >&2
  exit 2
fi
if ! psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d postgres -tAc 'select 1' >/dev/null 2>&1; then
  echo "FATAL: no PostgreSQL reachable at $PGHOST:$PGPORT as '$PGUSER'." >&2
  exit 2
fi

# Percent-encode the credentials before they go into a DSN. A password with an
# '@', '/', ':' or '?' in it — routine outside a demo stack — otherwise
# re-parses the authority section and every step fails with a connection error
# that reads like a migration or provisioning bug.
urlenc() {
  local s="$1" out="" c i
  for ((i = 0; i < ${#s}; i++)); do
    c="${s:i:1}"
    case "$c" in
      [a-zA-Z0-9.~_-]) out="$out$c" ;;
      *) out="$out$(printf '%%%02X' "'$c")" ;;
    esac
  done
  printf '%s' "$out"
}
SCRATCH_URL="postgresql+asyncpg://$(urlenc "$PGUSER"):$(urlenc "$PGPASSWORD")@$PGHOST:$PGPORT/$SCRATCH_DB"

# ---- helpers -----------------------------------------------------------------
q() { psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$SCRATCH_DB" -tAc "$1" 2>/dev/null | tr -d '\r'; }
alem() { ( cd "$ROOT/backend" && DATABASE_URL="$SCRATCH_URL" uv run alembic "$@" ); }
seed() { ( cd "$ROOT/backend" && DATABASE_URL="$SCRATCH_URL" uv run python -m entropia.apps.seed ); }

# The migration<->model parity comparison needs a SECOND database built from
# Base.metadata. It is derived from the scratch name, so the live-DB guard above
# covers it too, and it is torn down by the same trap rather than leaking on ^C.
PARITY_DB="${SCRATCH_DB}_model"

# Per-run log directory: fixed /tmp names are shared across runs and users, so a
# stale log from an earlier run can be quoted as evidence for this one.
LOGS="$(mktemp -d)"

reset_scratch() {
  dropdb -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" --if-exists "$SCRATCH_DB" >/dev/null 2>&1 || true
  createdb -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" "$SCRATCH_DB" || { bad "cannot create scratch DB '$SCRATCH_DB'"; return 1; }
}
cleanup() {
  if [ "${KEEP_SCRATCH:-0}" = "1" ]; then
    info "KEEP_SCRATCH=1 — leaving '$SCRATCH_DB' / '$PARITY_DB' and logs in $LOGS"
    return 0
  fi
  dropdb -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" --if-exists "$SCRATCH_DB" >/dev/null 2>&1 || true
  dropdb -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" --if-exists "$PARITY_DB" >/dev/null 2>&1 || true
  rm -rf "$LOGS"
}
trap cleanup EXIT INT TERM

# A shape-independent fingerprint over the rows a legacy fixture writes. It is
# computed from column VALUES, so it changes if an upgrade rewrites, drops or
# renumbers any of them — the only thing "data preserved" can honestly mean.
FIXTURE_FP_SQL="select coalesce(md5(string_agg(t, '|' order by t)), 'EMPTY') from (
  select user_id||username||coalesce(email,'')||display_name||\"current_role\"||version::text as t from human_users
  union all select instrument_id||resolution_key||symbol||registry_version::text from instrument_registry
  union all select event_id||event_kind||coalesce(reason,'') from audit_events
  union all select agent_id||name||enabled::text from agents
) x"

insert_domain_fixture() {
  psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$SCRATCH_DB" -v ON_ERROR_STOP=1 >/dev/null 2>&1 <<'SQL'
insert into principals (principal_id, principal_type) values
  ('user_legacy_admin','human'), ('agent_alpha','agent');
insert into human_users (user_id, username, email, display_name, "current_role")
  values ('user_legacy_admin','legacyadmin','legacy@entropia.local','Legacy Admin','admin');
insert into agents (agent_id, name) values ('agent_alpha','Alpha Agent');
insert into instrument_registry (instrument_id, resolution_key, venue_id, symbol, contract_type, display_name)
  values ('instr_legacy_1','legacy:btcusdt:spot','legacy','BTCUSDT','spot','BTC/USDT');
insert into audit_events (event_id, event_kind, actor_kind, actor_principal_id, reason)
  values ('evt_legacy_1','legacy.upgrade.probe','human','user_legacy_admin','pre-upgrade audit row');
SQL
}

banner() { printf '\n%s========== %s ==========%s\n' "$BOLD" "$*" "$RST"; }
banner "MIGRATION + PROVISIONING ACCEPTANCE  (scratch db: $SCRATCH_DB @ $PGHOST:$PGPORT)"

# =============================================================================
# [1] exactly one head
# =============================================================================
step "[1] the revision graph has exactly ONE head (no silent branch)"
HEADS_RAW="$(alem heads 2>/dev/null | grep -c '(head)')"
HEAD_REV="$(alem heads 2>/dev/null | grep '(head)' | head -n1 | awk '{print $1}')"
if [ "${HEADS_RAW:-0}" = "1" ] && [ -n "$HEAD_REV" ]; then
  ok "[1] single head: $HEAD_REV"
else
  bad "[1] expected exactly 1 head, found ${HEADS_RAW:-0} — a branched graph makes 'upgrade head' ambiguous"
fi

# =============================================================================
# [2] fresh install on an EMPTY database, via the real install path
# =============================================================================
step "[2] fresh install: empty database -> alembic upgrade head"
reset_scratch || { echo; exit 1; }
if alem upgrade head >"$LOGS"/a22_fresh.log 2>&1; then
  STAMPED="$(q 'select version_num from alembic_version')"
  TABLES="$(q "select count(*) from information_schema.tables where table_schema='public'")"
  if [ "$STAMPED" = "$HEAD_REV" ] && [ "${TABLES:-0}" -gt 1 ]; then
    ok "[2] empty -> head ($STAMPED), $TABLES public tables — no metadata.create_all on the install path"
  else
    bad "[2] stamped='$STAMPED' (want '$HEAD_REV'), tables=$TABLES"
  fi
else
  bad "[2] alembic upgrade head FAILED:"; sed 's/^/      /' "$LOGS"/a22_fresh.log | tail -20
fi

# =============================================================================
# [3] migration <-> model COLUMN parity
# =============================================================================
step "[3] migration<->model column parity (the migrated schema IS the ORM schema)"
dropdb -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" --if-exists "$PARITY_DB" >/dev/null 2>&1 || true
if createdb -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" "$PARITY_DB" >/dev/null 2>&1; then
  ( cd "$ROOT/backend" && DATABASE_URL="postgresql+asyncpg://$PGUSER:$PGPASSWORD@$PGHOST:$PGPORT/$PARITY_DB" \
      uv run python -c "
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
import entropia.infrastructure.postgres.models  # noqa: F401
from entropia.infrastructure.postgres.base import Base
from entropia.config import get_settings

async def main() -> None:
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()

asyncio.run(main())
" ) >"$LOGS"/a22_parity_build.log 2>&1
  COLQ="select table_name||'.'||column_name||':'||data_type||':'||is_nullable||':'||coalesce(character_maximum_length::text,'-') from information_schema.columns where table_schema='public' and table_name<>'alembic_version' order by 1"
  psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$SCRATCH_DB" -tAc "$COLQ" 2>/dev/null > "$LOGS"/a22_cols_migrated.txt
  psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PARITY_DB" -tAc "$COLQ" 2>/dev/null > "$LOGS"/a22_cols_model.txt
  N_MIG="$(wc -l < "$LOGS"/a22_cols_migrated.txt | tr -d ' ')"
  if [ "${N_MIG:-0}" -gt 0 ] && diff -q "$LOGS"/a22_cols_migrated.txt "$LOGS"/a22_cols_model.txt >/dev/null 2>&1; then
    ok "[3] $N_MIG columns identical (name, type, nullability, length) between migrations and Base.metadata"
  else
    bad "[3] column parity BROKEN — migrations and the ORM models disagree:"
    diff "$LOGS"/a22_cols_migrated.txt "$LOGS"/a22_cols_model.txt | head -30 | sed 's/^/      /'
  fi
  dropdb -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" --if-exists "$PARITY_DB" >/dev/null 2>&1 || true
else
  bad "[3] could not create the parity database '$PARITY_DB'"
fi
info "[3] scope is COLUMN parity, the axis CONTRIBUTING names. INDEX NAMES are known to"
info "    diverge (a migration-named index vs the model's autogenerated name) and are"
info "    deliberately NOT gated here — see docs/INSTALL_ACCEPTANCE.md 'Honest boundaries'."

# =============================================================================
# [4] migration-provisioned rows exist on the real install path
# =============================================================================
step "[4] rows a MIGRATION provisions land on the install path (agent_runtime singleton)"
RUNTIME_ROWS="$(q 'select count(*) from agent_runtime')"
RUNTIME_ID="$(q 'select agent_id from agent_runtime limit 1')"
if [ "${RUNTIME_ROWS:-0}" = "1" ] && [ "$RUNTIME_ID" = "alpha-agent" ]; then
  ok "[4] exactly one agent_runtime row, id='alpha-agent' (seeded by migration 0016_analysis_lab)"
else
  bad "[4] agent_runtime rows=$RUNTIME_ROWS id='$RUNTIME_ID' (want 1 / 'alpha-agent')"
fi

# =============================================================================
# [5] representative LEGACY revisions -> head, data preserved
# =============================================================================
step "[5] representative legacy revisions upgrade to head with existing rows preserved"

# 5a — the earliest installable state. Only app_metadata exists at 0001, so the
# fixture is that table; the point of this case is the FULL 42-step climb.
LEGACY_EARLY="0001_initial"
reset_scratch || true
if alem upgrade "$LEGACY_EARLY" >"$LOGS"/a22_l1.log 2>&1; then
  psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$SCRATCH_DB" -v ON_ERROR_STOP=1 >/dev/null 2>&1 \
    -c "insert into app_metadata (key, value) values ('adim22.legacy_probe','installed-at-0001')"
  BEFORE="$(q "select value from app_metadata where key='adim22.legacy_probe'")"
  if alem upgrade head >>"$LOGS"/a22_l1.log 2>&1; then
    AFTER="$(q "select value from app_metadata where key='adim22.legacy_probe'")"
    STAMPED="$(q 'select version_num from alembic_version')"
    if [ -n "$BEFORE" ] && [ "$AFTER" = "$BEFORE" ] && [ "$STAMPED" = "$HEAD_REV" ]; then
      ok "[5a] $LEGACY_EARLY -> head: pre-existing row preserved verbatim ('$AFTER'), stamped $STAMPED"
    else
      bad "[5a] before='$BEFORE' after='$AFTER' stamped='$STAMPED'"
    fi
  else
    bad "[5a] $LEGACY_EARLY -> head FAILED:"; tail -20 "$LOGS"/a22_l1.log | sed 's/^/      /'
  fi
else
  bad "[5a] could not build the $LEGACY_EARLY legacy state"; tail -10 "$LOGS"/a22_l1.log | sed 's/^/      /'
fi

# 5b — a mid-life state carrying real identity + domain + audit rows.
LEGACY_MID="${MIGRATION_ACCEPTANCE_LEGACY_REV:-0030_precheck_source_warnings}"
reset_scratch || true
if alem upgrade "$LEGACY_MID" >"$LOGS"/a22_l2.log 2>&1; then
  if insert_domain_fixture; then
    BEFORE="$(q "$FIXTURE_FP_SQL")"
    if alem upgrade head >>"$LOGS"/a22_l2.log 2>&1; then
      AFTER="$(q "$FIXTURE_FP_SQL")"
      STAMPED="$(q 'select version_num from alembic_version')"
      if [ "$BEFORE" != "EMPTY" ] && [ "$AFTER" = "$BEFORE" ] && [ "$STAMPED" = "$HEAD_REV" ]; then
        ok "[5b] $LEGACY_MID -> head: identity/domain/audit fixture byte-identical (fp $AFTER), stamped $STAMPED"
      else
        bad "[5b] fingerprint changed across the upgrade: '$BEFORE' -> '$AFTER' (stamped '$STAMPED')"
      fi
    else
      bad "[5b] $LEGACY_MID -> head FAILED:"; tail -20 "$LOGS"/a22_l2.log | sed 's/^/      /'
    fi
  else
    bad "[5b] could not write the legacy fixture at $LEGACY_MID"
  fi
else
  bad "[5b] could not build the $LEGACY_MID legacy state"; tail -10 "$LOGS"/a22_l2.log | sed 's/^/      /'
fi

# =============================================================================
# [6] the latest revision down/up round-trips and preserves data
# =============================================================================
# Runs on the SAME database [5b] left at head with the fixture in place, so the
# round trip is measured against real rows rather than an empty schema.
step "[6] latest revision down/up/up preserves the data that survives it"
BEFORE="$(q "$FIXTURE_FP_SQL")"
# Without this guard the step is vacuous whenever [5b] failed to write its
# fixture: 'EMPTY' == 'EMPTY' would report the round trip as data-preserving on
# an empty schema, which is the one thing this step must never claim.
if [ "$BEFORE" = "EMPTY" ] || [ -z "$BEFORE" ]; then
  bad "[6] no fixture rows to measure (step [5b] left the database empty) — a down/up over an empty schema proves nothing"
elif alem downgrade -1 >"$LOGS"/a22_du.log 2>&1; then
  MID="$(q 'select version_num from alembic_version')"
  if alem upgrade head >>"$LOGS"/a22_du.log 2>&1; then
    AFTER="$(q "$FIXTURE_FP_SQL")"
    STAMPED="$(q 'select version_num from alembic_version')"
    if [ "$AFTER" = "$BEFORE" ] && [ "$STAMPED" = "$HEAD_REV" ]; then
      ok "[6] head -> $MID -> head: fixture unchanged (fp $AFTER), back at $STAMPED"
    else
      bad "[6] round trip lost data: '$BEFORE' -> '$AFTER' (stamped '$STAMPED')"
    fi
  else
    bad "[6] re-upgrade after downgrade FAILED:"; tail -20 "$LOGS"/a22_du.log | sed 's/^/      /'
  fi
else
  bad "[6] downgrade -1 FAILED — the head revision has no working downgrade:"; tail -20 "$LOGS"/a22_du.log | sed 's/^/      /'
fi

# =============================================================================
# [7] provisioning is REPEAT-idempotent
# =============================================================================
step "[7] provisioning (python -m entropia.apps.seed) is repeat-idempotent"
reset_scratch || true
alem upgrade head >/dev/null 2>&1
COUNTS_SQL="select 'principals='||(select count(*) from principals)||' agents='||(select count(*) from agents)||' human_users='||(select count(*) from human_users)||' capabilities='||(select count(*) from future_capability)||' agent_runtime='||(select count(*) from agent_runtime)"
R1=0; seed >"$LOGS"/a22_seed1.log 2>&1 || R1=$?
C1="$(q "$COUNTS_SQL")"
R2=0; seed >"$LOGS"/a22_seed2.log 2>&1 || R2=$?
C2="$(q "$COUNTS_SQL")"
if [ "$R1" -eq 0 ] && [ "$R2" -eq 0 ]; then
  ok "[7] both provisioning runs exit 0"
else
  bad "[7] provisioning exit codes: run1=$R1 run2=$R2 (want 0/0)"; tail -6 "$LOGS"/a22_seed2.log | sed 's/^/      /'
fi
if [ -n "$C1" ] && [ "$C1" = "$C2" ]; then
  ok "[7] state unchanged by the repeat: $C2"
else
  bad "[7] repeat changed the state: '$C1' -> '$C2'"
fi

# =============================================================================
# [8] provisioning is CONCURRENT-idempotent
# =============================================================================
# The compose `provision` one-shot is a hard `service_completed_successfully`
# gate for every plane, so a provisioning run that exits non-zero because
# another one was racing it stops the whole stack from starting.
step "[8] provisioning is concurrent-idempotent (parallel runs, no crash, no reset)"
reset_scratch || true
alem upgrade head >/dev/null 2>&1
PIDS=""; i=1
while [ "$i" -le 3 ]; do
  seed >"$LOGS"/a22_conc_$i.log 2>&1 &
  PIDS="$PIDS $!"
  i=$((i+1))
done
CONC_FAIL=0
for p in $PIDS; do wait "$p" || CONC_FAIL=$((CONC_FAIL+1)); done
C_CONC="$(q "$COUNTS_SQL")"
if [ "$CONC_FAIL" -eq 0 ]; then
  ok "[8] all 3 concurrent provisioning runs exit 0"
else
  bad "[8] $CONC_FAIL of 3 concurrent provisioning runs exited non-zero — the compose 'provision' gate would block every plane:"
  grep -h -m1 -E 'UniqueViolation|IntegrityError|DuplicateObject' "$LOGS"/a22_conc_*.log 2>/dev/null | head -3 | sed 's/^/      /'
fi
# A second, sequential run must still be a no-op: concurrency must not have left
# the database in a state a later provisioning would "repair" by writing again.
seed >"$LOGS"/a22_conc_after.log 2>&1
C_AFTER="$(q "$COUNTS_SQL")"
if [ -n "$C_CONC" ] && [ "$C_CONC" = "$C_AFTER" ] && [ "$C_CONC" = "$C2" ]; then
  ok "[8] concurrent result equals the sequential result and is stable: $C_AFTER"
else
  bad "[8] state diverged — sequential='$C2' concurrent='$C_CONC' after-repair='$C_AFTER'"
fi

# =============================================================================
banner "RESULT"
printf '  %s%d passed%s, %s%d failed%s\n' "$GRN" "$PASS_N" "$RST" "$RED" "$FAIL_N" "$RST"
if [ "$FAIL_N" -eq 0 ]; then
  echo "MIGRATION ACCEPTANCE OK — fresh install, legacy upgrade, down/up and provisioning all hold."
  exit 0
fi
echo "MIGRATION ACCEPTANCE FAILED — see the FAIL lines above."
exit 1
