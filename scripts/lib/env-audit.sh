#!/usr/bin/env bash
# =============================================================================
# scripts/lib/env-audit.sh — shared, non-destructive .env inspection/migration
# helpers (POSIX-friendly bash). Sourced by update.sh and
# configure-local-session.sh.  DEP-03: never echoes a secret VALUE, only key
# NAMES; every mutation is idempotent and backup-guarded by the caller.
# =============================================================================

# Idempotent source guard — safe if two callers source this in one shell.
[ -n "${_ENV_AUDIT_SH:-}" ] && return 0
_ENV_AUDIT_SH=1

# The file every helper reads/writes. Callers may override before sourcing.
ENV_FILE="${ENV_FILE:-.env}"

# Keys that must be present AND non-empty for any coherent local run.
ENV_REQUIRED_ALWAYS="ENTROPIA_ENV AUTH_MODE DATABASE_URL"
# Additionally required (non-empty) only under AUTH_MODE=session.
ENV_REQUIRED_SESSION="ENTROPIA_SERVICE_TOKEN"
# Sensitive keys: never auto-filled from the example, values never printed.
ENV_SECRET_KEYS="POSTGRES_PASSWORD OBJECT_STORAGE_ACCESS_KEY OBJECT_STORAGE_SECRET_KEY ENTROPIA_SERVICE_TOKEN ENTROPIA_BOOTSTRAP_ADMIN_EMAIL"

# True (0) if KEY has a non-empty value.
env_has() { grep -qE "^$1=.+$" "$ENV_FILE" 2>/dev/null; }
# True (0) if a line for KEY exists at all (even KEY= with an empty value).
env_line_exists() { grep -qE "^$1=" "$ENV_FILE" 2>/dev/null; }
# Echo KEY's raw value. Callers MUST NOT print the result for secret keys.
env_get() { [ -f "$ENV_FILE" ] || return 0; sed -n "s/^$1=//p" "$ENV_FILE" | head -n1; }

# True (0) if KEY is sensitive (excluded from example backfill + logging).
env_is_secret() {
  case " $ENV_SECRET_KEYS " in *" $1 "*) return 0 ;; *) return 1 ;; esac
}

# Idempotently set KEY=VALUE: replace an existing line in place or append a new
# one. Never prints VALUE. awk rebuilds only the matched line, so every other
# line (comments, blanks, other secrets) is preserved byte-for-byte.
env_set() {
  key="$1"; val="$2"; _tmp="$(mktemp)"
  if env_line_exists "$key"; then
    awk -v k="$key" -v v="$val" \
      '{ eq=index($0,"="); if (eq>0 && substr($0,1,eq-1)==k) print k"="v; else print }' \
      "$ENV_FILE" > "$_tmp"
  else
    cp "$ENV_FILE" "$_tmp"
    printf '%s=%s\n' "$key" "$val" >> "$_tmp"
  fi
  mv "$_tmp" "$ENV_FILE"
}

# Timestamped, permission-tight backup of .env. Echoes the backup PATH (never
# contents); no-op (empty output) when there is no .env yet.
env_backup() {
  [ -f "$ENV_FILE" ] || return 0
  _ts="$(date +%Y%m%d-%H%M%S)"; _dst="${ENV_FILE}.bak.${_ts}"; _n=1
  while [ -e "$_dst" ]; do _dst="${ENV_FILE}.bak.${_ts}.${_n}"; _n=$((_n + 1)); done
  cp "$ENV_FILE" "$_dst"
  chmod 600 "$_dst" 2>/dev/null || true
  printf '%s' "$_dst"
}

# Print (space-separated) the non-secret keys present in the example but missing
# from .env — the safe backfill set. Names only, no values, no mutation.
env_missing_example_keys() {
  _example="${1:-.env.example}"; _out=""
  [ -f "$_example" ] || return 0
  while IFS= read -r _line; do
    case "$_line" in \#*|"") continue ;; esac
    case "$_line" in *=*) : ;; *) continue ;; esac
    _key="${_line%%=*}"
    env_is_secret "$_key" && continue
    env_line_exists "$_key" && continue
    _out="$_out $_key"
  done < "$_example"
  printf '%s' "${_out# }"
}

# Append every safe missing example key (verbatim example line, comment and all,
# matching a fresh `cp .env.example .env`). Echoes the appended NAMES. The caller
# is responsible for taking an env_backup first.
env_append_missing_from_example() {
  _example="${1:-.env.example}"; _added=""
  [ -f "$_example" ] || return 0
  for _key in $(env_missing_example_keys "$_example"); do
    _line="$(grep -E "^${_key}=" "$_example" | head -n1)"
    [ -n "$_line" ] || continue
    printf '%s\n' "$_line" >> "$ENV_FILE"
    _added="$_added $_key"
  done
  printf '%s' "${_added# }"
}

# Print (space-separated) the unresolved required keys for the .env's own
# AUTH_MODE. Empty output = configuration is complete. Names only.
env_unresolved_required() {
  _mode="$(env_get AUTH_MODE)"; _missing=""
  for _k in $ENV_REQUIRED_ALWAYS; do env_has "$_k" || _missing="$_missing $_k"; done
  if [ "$_mode" = "session" ]; then
    for _k in $ENV_REQUIRED_SESSION; do env_has "$_k" || _missing="$_missing $_k"; done
  fi
  printf '%s' "${_missing# }"
}
