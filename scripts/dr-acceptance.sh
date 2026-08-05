#!/usr/bin/env bash
# =============================================================================
# Entropia — DISASTER-RECOVERY acceptance (ADIM 22).
#
# `scripts/backup-verify.sh` answers "does the dump load?" (alembic head +
# table count). That is a coherence check, not a recovery proof: a dump that
# lost every row, every immutable hash and every audit event still passes it.
#
# This harness proves the RESTORE actually recovers the installation:
#
#   [1] take a real backup of the live database (scripts/backup.sh)
#   [2] restore it into a SCRATCH database (scripts/restore.sh RESTORE_DB=...)
#   [3] alembic head identical
#   [4] the public table SET is identical
#   [5] EVERY table's row count is identical (all tables, not a sample)
#   [6] immutable evidence is byte-identical: revision content hashes, run/
#       result manifest hashes + composition fingerprints, export checksums
#   [7] the append-only planes are identical: audit_events, outbox_events,
#       agent_checkpoint
#   [8] object storage round-trips byte-for-byte (per-object md5), when the
#       backup captured it
#
#   scripts/dr-acceptance.sh                 # back up the live DB, restore to scratch
#   scripts/dr-acceptance.sh ./backups/<ts>  # verify an EXISTING backup dir
#   DR_SCRATCH_DB=my_scratch scripts/dr-acceptance.sh
#
# What this harness writes, and nothing else:
#   * ./backups/dr-acceptance/<stamp>/   its own backup directory, with its own
#     retention scope — `backup.sh` prunes inside whatever BACKUP_DIR it is
#     given, so it must never be pointed at the operator's ./backups.
#   * a scratch DATABASE   (DR_SCRATCH_DB, must differ from the source)
#   * a scratch BUCKET     (DR_SCRATCH_BUCKET, must differ from the live one)
# The source database and the live bucket are only ever READ. Both scratch
# targets are guarded by name and removed on exit. This matters: `restore.sh`'s
# RESTORE_DB scopes only its Postgres half — without the bucket override, the
# object half mirrors the backup straight back into the LIVE bucket and reverts
# every artifact key written since the backup was taken.
#
# Exit code: 0 = the backup recovers the installation, 1 = it does not,
# 2 = the environment is not usable.
# =============================================================================
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"

BOLD=$'\033[1m'; DIM=$'\033[2m'; RED=$'\033[31m'; GRN=$'\033[32m'; YEL=$'\033[33m'; CYA=$'\033[36m'; RST=$'\033[0m'
PASS_N=0; FAIL_N=0; WARN_N=0
step()  { printf '\n%s— %s%s\n' "$CYA" "$*" "$RST"; }
ok()    { PASS_N=$((PASS_N+1)); printf '  %sPASS%s  %s\n' "$GRN" "$RST" "$*"; }
bad()   { FAIL_N=$((FAIL_N+1)); printf '  %sFAIL%s  %s\n' "$RED" "$RST" "$*"; }
warn()  { WARN_N=$((WARN_N+1)); printf '  %sWARN%s  %s\n' "$YEL" "$RST" "$*"; }
info()  { printf '  %s%s%s\n' "$DIM" "$*" "$RST"; }
banner(){ printf '\n%s========== %s ==========%s\n' "$BOLD" "$*" "$RST"; }

env_get() {
  [ -f "$ROOT/.env" ] || return 0
  sed -n "s/^$1=//p" "$ROOT/.env" | tail -1 | sed 's/[[:space:]]*#.*$//; s/^[[:space:]]*//; s/[[:space:]]*$//'
}

PGHOST="${BACKUP_PGHOST:-localhost}"
PGPORT="${BACKUP_PGPORT:-5432}"
PGUSER="${POSTGRES_USER:-$(env_get POSTGRES_USER)}"; PGUSER="${PGUSER:-entropia}"
_pgpass="${POSTGRES_PASSWORD:-$(env_get POSTGRES_PASSWORD)}"; export PGPASSWORD="${_pgpass:-entropia}"
SRC_DB="${POSTGRES_DB:-$(env_get POSTGRES_DB)}"; SRC_DB="${SRC_DB:-entropia}"
SCRATCH_DB="${DR_SCRATCH_DB:-entropia_dr_acceptance}"

# ---- object storage: live (read-only) vs scratch (restore target) ------------
# `restore.sh`'s RESTORE_DB only scopes the POSTGRES half; its object half
# resolves the bucket from the environment and mirrors INTO it. Restoring with
# the live bucket in scope would silently revert every artifact key written
# since the backup — on the operator's running stack. So the restore is pointed
# at a scratch bucket, which is also what makes step [8] non-circular: it
# compares the backup mirror against what the RESTORE wrote, not against the
# live bucket the backup was just read from.
_obj_raw="${OBJECT_STORAGE_ENDPOINT:-$(env_get OBJECT_STORAGE_ENDPOINT)}"; _obj_raw="${_obj_raw:-http://minio:9000}"
OBJ_ENDPOINT="${BACKUP_OBJECT_ENDPOINT:-$(printf '%s' "$_obj_raw" | sed 's#//minio:#//localhost:#')}"
OBJ_AK="${OBJECT_STORAGE_ACCESS_KEY:-$(env_get OBJECT_STORAGE_ACCESS_KEY)}"; OBJ_AK="${OBJ_AK:-entropia}"
OBJ_SK="${OBJECT_STORAGE_SECRET_KEY:-$(env_get OBJECT_STORAGE_SECRET_KEY)}"; OBJ_SK="${OBJ_SK:-entropia-secret}"
LIVE_BUCKET="${OBJECT_STORAGE_BUCKET:-$(env_get OBJECT_STORAGE_BUCKET)}"; LIVE_BUCKET="${LIVE_BUCKET:-entropia-artifacts}"
SCRATCH_BUCKET="${DR_SCRATCH_BUCKET:-entropia-dr-acceptance}"
if [ "$SCRATCH_BUCKET" = "$LIVE_BUCKET" ]; then
  echo "FATAL: DR_SCRATCH_BUCKET ('$SCRATCH_BUCKET') must differ from the live bucket ('$LIVE_BUCKET')." >&2
  exit 2
fi

# `backup.sh` prunes to BACKUP_RETENTION inside whatever directory it is given.
# Pointed at ./backups that would delete the operator's real backups, so this
# harness keeps its own subdirectory with its own retention scope.
export BACKUP_DIR="${DR_BACKUP_DIR:-$ROOT/backups/dr-acceptance}"
export BACKUP_RETENTION="${DR_BACKUP_RETENTION:-3}"

for t in psql pg_dump pg_restore createdb dropdb; do
  command -v "$t" >/dev/null 2>&1 || { echo "FATAL: $t not found — install the PostgreSQL client tools." >&2; exit 2; }
done
if [ "$SCRATCH_DB" = "$SRC_DB" ]; then
  echo "FATAL: DR_SCRATCH_DB ('$SCRATCH_DB') must differ from the source database ('$SRC_DB')." >&2
  exit 2
fi
if ! psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$SRC_DB" -tAc 'select 1' >/dev/null 2>&1; then
  echo "FATAL: source database '$SRC_DB' unreachable at $PGHOST:$PGPORT as '$PGUSER'." >&2
  exit 2
fi

qs() { psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$SRC_DB"     -tAc "$1" 2>/dev/null | tr -d '\r'; }
qd() { psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$SCRATCH_DB" -tAc "$1" 2>/dev/null | tr -d '\r'; }

WORK="$(mktemp -d)"

# mc invocation that works with a host binary or a dockerized one. Returns 1
# when neither is available, so callers WARN instead of silently passing.
mc_run() {
  # mc_run <local-dir-to-mount> <shell snippet using `mc`>
  local mount="$1" snippet="$2"
  if command -v mc >/dev/null 2>&1; then
    ( export MC_HOST_dr="http://$OBJ_AK:$OBJ_SK@${OBJ_ENDPOINT#http://}"
      DR="dr"; MOUNT="$mount"; eval "$snippet" ) >/dev/null 2>&1
  elif command -v docker >/dev/null 2>&1; then
    local ep="${OBJ_ENDPOINT/localhost/host.docker.internal}"
    docker run --rm --add-host=host.docker.internal:host-gateway -v "$mount:/mnt" \
      -e "MC_HOST_dr=http://$OBJ_AK:$OBJ_SK@${ep#http://}" \
      minio/mc:latest sh -c "DR=dr; MOUNT=/mnt; $snippet" >/dev/null 2>&1
  else
    return 1
  fi
}

cleanup() {
  if [ "${DR_KEEP_SCRATCH:-0}" != "1" ]; then
    dropdb -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" --if-exists "$SCRATCH_DB" >/dev/null 2>&1 || true
    # The scratch bucket is this harness's own; never the live one (guarded above).
    mc_run "$WORK" 'mc rb --force "$DR/'"$SCRATCH_BUCKET"'"' || true
  fi
  rm -rf "$WORK"
}
trap cleanup EXIT INT TERM

banner "DR ACCEPTANCE  (source '$SRC_DB' -> scratch '$SCRATCH_DB' @ $PGHOST:$PGPORT)"

# =============================================================================
# [1] backup
# =============================================================================
SRC_BACKUP="${1:-}"
if [ -n "$SRC_BACKUP" ]; then
  step "[1] using the supplied backup directory"
  if [ -f "$SRC_BACKUP/postgres.dump" ]; then
    ok "[1] $SRC_BACKUP/postgres.dump present ($(wc -c < "$SRC_BACKUP/postgres.dump" | tr -d ' ') bytes)"
  else
    bad "[1] $SRC_BACKUP/postgres.dump not found — not a backup directory"; banner "RESULT"; exit 1
  fi
else
  step "[1] take a real backup of the live database (scripts/backup.sh)"
  if bash scripts/backup.sh >"$WORK/backup.log" 2>&1; then
    SRC_BACKUP="$(sed -n 's/^BACKUP OK — //p' "$WORK/backup.log" | tail -1)"
    if [ -n "$SRC_BACKUP" ] && [ -f "$SRC_BACKUP/postgres.dump" ]; then
      ok "[1] backup written: $SRC_BACKUP"
      grep -E '^ +(PASS|WARN)' "$WORK/backup.log" | sed 's/^/      /'
    else
      bad "[1] backup.sh reported success but produced no readable dump"; sed 's/^/      /' "$WORK/backup.log" | tail -15
      banner "RESULT"; exit 1
    fi
  else
    bad "[1] scripts/backup.sh FAILED:"; sed 's/^/      /' "$WORK/backup.log" | tail -20
    banner "RESULT"; exit 1
  fi
fi

# Object-storage fingerprint of the backup mirror, captured BEFORE the restore.
OBJ_IN_BACKUP=false
if [ -d "$SRC_BACKUP/minio" ]; then
  OBJ_IN_BACKUP=true
  ( cd "$SRC_BACKUP/minio" && find . -type f | sort | while IFS= read -r f; do
      printf '%s %s %s\n' "$f" "$(wc -c < "$f" | tr -d ' ')" "$( (md5sum "$f" 2>/dev/null || md5 -q "$f") | awk '{print $1}')"
    done ) > "$WORK/obj_backup.txt"
fi

# =============================================================================
# [2] restore into a scratch database
# =============================================================================
step "[2] restore into the scratch database and the scratch bucket (the live stack is not written)"
dropdb -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" --if-exists "$SCRATCH_DB" >/dev/null 2>&1 || true
createdb -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" "$SCRATCH_DB" >/dev/null 2>&1 \
  || { bad "[2] cannot create scratch DB '$SCRATCH_DB'"; banner "RESULT"; exit 1; }
# RESTORE_DB scopes the Postgres half; OBJECT_STORAGE_BUCKET scopes the object
# half. Both are required — with only the first, restore.sh mirrors the backup's
# objects straight back into the LIVE bucket and reverts every key written since.
if RESTORE_DB="$SCRATCH_DB" OBJECT_STORAGE_BUCKET="$SCRATCH_BUCKET" \
     bash scripts/restore.sh "$SRC_BACKUP" --yes >"$WORK/restore.log" 2>&1; then
  ok "[2] restore.sh completed into '$SCRATCH_DB' (+ bucket '$SCRATCH_BUCKET')"
else
  bad "[2] scripts/restore.sh FAILED:"; sed 's/^/      /' "$WORK/restore.log" | tail -20
  banner "RESULT"; exit 1
fi

# =============================================================================
# [3] alembic head
# =============================================================================
step "[3] the restored database is stamped at the same Alembic revision"
S_HEAD="$(qs 'select version_num from alembic_version')"
D_HEAD="$(qd 'select version_num from alembic_version')"
if [ -n "$S_HEAD" ] && [ "$S_HEAD" = "$D_HEAD" ]; then
  ok "[3] alembic head identical: $D_HEAD"
else
  bad "[3] alembic head differs: source='$S_HEAD' restored='$D_HEAD'"
fi

# =============================================================================
# [4] table set
# =============================================================================
step "[4] the public table set is identical"
TBLQ="select table_name from information_schema.tables where table_schema='public' order by 1"
qs "$TBLQ" > "$WORK/tbl_src.txt"; qd "$TBLQ" > "$WORK/tbl_dst.txt"
N_TBL="$(wc -l < "$WORK/tbl_src.txt" | tr -d ' ')"
if [ "${N_TBL:-0}" -gt 0 ] && diff -q "$WORK/tbl_src.txt" "$WORK/tbl_dst.txt" >/dev/null 2>&1; then
  ok "[4] $N_TBL public tables, same set"
else
  bad "[4] table set differs:"; diff "$WORK/tbl_src.txt" "$WORK/tbl_dst.txt" | head -20 | sed 's/^/      /'
fi

# =============================================================================
# [5] per-table row counts — every table, not a sample
# =============================================================================
step "[5] every table's row count survives the round trip"
COUNTQ="select table_name||'='||(xpath('/row/cnt/text()', query_to_xml(format('select count(*) as cnt from %I.%I','public',table_name), false, true, '')))[1]::text
        from information_schema.tables where table_schema='public' and table_type='BASE TABLE' order by table_name"
qs "$COUNTQ" > "$WORK/cnt_src.txt"; qd "$COUNTQ" > "$WORK/cnt_dst.txt"
NONEMPTY="$(grep -v '=0$' "$WORK/cnt_src.txt" 2>/dev/null | wc -l | tr -d ' ')"
TOTAL_ROWS="$(awk -F= '{s+=$2} END {print s+0}' "$WORK/cnt_src.txt")"
if diff -q "$WORK/cnt_src.txt" "$WORK/cnt_dst.txt" >/dev/null 2>&1; then
  ok "[5] row counts identical across all tables ($TOTAL_ROWS rows, $NONEMPTY non-empty tables)"
else
  bad "[5] row counts diverged:"; diff "$WORK/cnt_src.txt" "$WORK/cnt_dst.txt" | head -20 | sed 's/^/      /'
fi
if [ "${TOTAL_ROWS:-0}" -eq 0 ]; then
  warn "[5] the source database is EMPTY — a restore of nothing proves nothing. Seed or use a live stack before trusting this run."
fi

# =============================================================================
# [6] immutable evidence — hashes, fingerprints, manifests, checksums
# =============================================================================
# These are the columns V1 promises never change once written. A restore that
# renumbers or drops one of them silently invalidates every pinned artifact.
step "[6] immutable evidence is byte-identical (revision/manifest/result hashes, checksums)"
evidence_fp() {
  # evidence_fp <db-fn> <table> <expr>  -> md5 over the ordered projection
  local fn="$1" table="$2" expr="$3"
  $fn "select coalesce(md5(string_agg(t, '|' order by t)), 'EMPTY') from (select ($expr)::text as t from $table) x"
}
EVIDENCE="entity_revisions|entity_id||revision_no::text||coalesce(content_hash,'')
backtest_run_manifest|manifest_id||coalesce(manifest_hash,'')||coalesce(composition_fingerprint,'')
backtest_result|result_id||coalesce(manifest_hash,'')||coalesce(manifest_id,'')||coalesce(composition_fingerprint,'')
market_dataset_revision|entity_id||revision_no::text||coalesce(content_hash,'')||coalesce(manifest_hash,'')
research_dataset_revision|entity_id||revision_no::text||coalesce(content_hash,'')||coalesce(manifest_hash,'')
package_revision|entity_id||revision_no::text||coalesce(content_hash,'')
rationale_family_revision|entity_id||revision_no::text||coalesce(content_hash,'')
strategy_revision|revision_id||revision_number::text||coalesce(content_hash,'')||coalesce(config_hash,'')
export_artifact|export_id||coalesce(checksum,'')||coalesce(source_manifest_hash,'')||coalesce(object_key,'')
manual_document_revisions|revision_id||revision_no::text||coalesce(content_checksum,'')"
EV_FAIL=0; EV_SEEN=0; EV_NONEMPTY=0
while IFS='|' read -r tbl expr; do
  [ -z "$tbl" ] && continue
  s="$(evidence_fp qs "$tbl" "$expr")"; d="$(evidence_fp qd "$tbl" "$expr")"
  if [ -z "$s" ] || [ -z "$d" ]; then
    bad "[6] $tbl — could not project the evidence columns (missing table/column?)"; EV_FAIL=1; continue
  fi
  if [ "$s" = "$d" ]; then
    EV_SEEN=$((EV_SEEN+1))
    if [ "$s" = "EMPTY" ]; then
      info "[6] $tbl — no rows (fingerprint EMPTY on both sides)"
    else
      EV_NONEMPTY=$((EV_NONEMPTY+1)); info "[6] $tbl — $s"
    fi
  else
    bad "[6] $tbl evidence CHANGED: source=$s restored=$d"; EV_FAIL=1
  fi
done <<EOF
$EVIDENCE
EOF
[ "$EV_FAIL" -eq 0 ] && ok "[6] all $EV_SEEN immutable-evidence projections identical ($EV_NONEMPTY carried rows)"
# An EMPTY==EMPTY comparison is a true statement about nothing. Say so out loud
# rather than let an unseeded source database read as a strong DR result.
if [ "$EV_FAIL" -eq 0 ] && [ "$EV_NONEMPTY" -lt 2 ]; then
  warn "[6] only $EV_NONEMPTY evidence table(s) actually held rows — this run proves little about hash preservation."
  info "[6] Seed the source stack first (SEED_E2E_GOLDEN=1 SEED_ESP_TA=1 SEED_RATIONALE=1) so revisions, manifests and results exist."
fi

# =============================================================================
# [7] append-only planes
# =============================================================================
step "[7] audit, outbox and agent checkpoints survive intact"
APPEND="audit_events|event_id||event_kind||coalesce(payload_hash_before,'')||coalesce(payload_hash_after,'')||coalesce(correlation_id,'')
outbox_events|id||event_type||resource_type||resource_id||coalesce(correlation_id,'')||attempts::text
agent_checkpoint|checkpoint_id||coalesce(context_manifest_id,'')"
AP_FAIL=0; AP_NONEMPTY=0
while IFS='|' read -r tbl expr; do
  [ -z "$tbl" ] && continue
  s="$(evidence_fp qs "$tbl" "$expr")"; d="$(evidence_fp qd "$tbl" "$expr")"
  n="$(qs "select count(*) from $tbl")"
  if [ -n "$s" ] && [ "$s" = "$d" ]; then
    [ "$s" = "EMPTY" ] || AP_NONEMPTY=$((AP_NONEMPTY+1))
    info "[7] $tbl — ${n:-?} rows, fingerprint $s"
  else
    bad "[7] $tbl diverged: source=$s restored=$d"; AP_FAIL=1
  fi
done <<EOF
$APPEND
EOF
[ "$AP_FAIL" -eq 0 ] && ok "[7] audit_events / outbox_events / agent_checkpoint identical ($AP_NONEMPTY carried rows)"
# Same honesty rule as [6]: three empty tables comparing equal is not evidence.
if [ "$AP_FAIL" -eq 0 ] && [ "$AP_NONEMPTY" -eq 0 ]; then
  warn "[7] all three append-only planes were EMPTY — this run proves nothing about audit/outbox preservation."
fi

# =============================================================================
# [8] object storage round trip
# =============================================================================
# Compared against the SCRATCH bucket the restore wrote — never the live bucket
# the backup was read from. Re-reading the source would be circular: step [2]
# would have put the backup's own bytes there, so a match would prove that
# `mc mirror` copies files, and any key written after the backup would show up
# as a spurious difference.
step "[8] object storage round-trips byte-for-byte into the restored bucket"
OBJ_REQUIRED="${DR_REQUIRE_OBJECTS:-0}"
obj_missing() {  # WARN by default; FAIL when the caller demanded object coverage
  if [ "$OBJ_REQUIRED" = "1" ]; then bad "[8] $1 (DR_REQUIRE_OBJECTS=1)"; else warn "[8] $1"; fi
}
if [ "$OBJ_IN_BACKUP" != true ]; then
  obj_missing "the backup captured no object storage (minio/ absent) — artifact BYTES are NOT covered by this run"
  info "[8] the DB still holds every URI + checksum; run against a stack with a reachable MinIO to cover the bytes."
else
  N_OBJ="$(wc -l < "$WORK/obj_backup.txt" | tr -d ' ')"
  mkdir -p "$WORK/objcheck"
  MIRRORED=false
  if ! curl -s --max-time 5 "$OBJ_ENDPOINT/minio/health/live" >/dev/null 2>&1; then
    obj_missing "object storage unreachable at $OBJ_ENDPOINT — cannot read the restored bytes"
  elif mc_run "$WORK/objcheck" 'mc mirror --overwrite "$DR/'"$SCRATCH_BUCKET"'" "$MOUNT"'; then
    MIRRORED=true
  else
    obj_missing "could not mirror the restored bucket '$SCRATCH_BUCKET' (no usable 'mc' or 'docker')"
  fi
  if [ "$MIRRORED" = true ]; then
    ( cd "$WORK/objcheck" && find . -type f | sort | while IFS= read -r f; do
        printf '%s %s %s\n' "$f" "$(wc -c < "$f" | tr -d ' ')" "$( (md5sum "$f" 2>/dev/null || md5 -q "$f") | awk '{print $1}')"
      done ) > "$WORK/obj_restored.txt"
    if diff -q "$WORK/obj_backup.txt" "$WORK/obj_restored.txt" >/dev/null 2>&1; then
      if [ "${N_OBJ:-0}" -gt 0 ]; then
        ok "[8] $N_OBJ objects: path, size and md5 identical between the backup and the RESTORED bucket"
      else
        obj_missing "the backup's object mirror was empty — zero artifact bytes were compared"
      fi
    else
      bad "[8] restored object bytes differ from the backup:"
      diff "$WORK/obj_backup.txt" "$WORK/obj_restored.txt" | head -20 | sed 's/^/      /'
    fi
  fi
fi

# =============================================================================
banner "RESULT"
printf '  %s%d passed%s, %s%d failed%s, %s%d warned%s\n' \
  "$GRN" "$PASS_N" "$RST" "$RED" "$FAIL_N" "$RST" "$YEL" "$WARN_N" "$RST"
info "backup under test: $SRC_BACKUP"
if [ "$FAIL_N" -eq 0 ]; then
  echo "DR ACCEPTANCE OK — the backup restores the installation, not just a loadable schema."
  exit 0
fi
echo "DR ACCEPTANCE FAILED — see the FAIL lines above."
exit 1
