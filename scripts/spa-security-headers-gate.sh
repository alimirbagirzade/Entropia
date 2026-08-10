#!/usr/bin/env bash
# =============================================================================
# Entropia — SPA origin security-header gate (P9-F2).
#
# The API's CSP is pinned by an assertion on a LIVE response
# (backend/tests/contract/test_hardening_contract.py). Until this script the
# STATIC origin — the one that serves the executable bundle — had no equivalent:
# its headers lived in a config file and nothing ever read them back off the
# wire. "It is written in the config" and "it is in the response" are different
# facts, and only the second one is the one a browser enforces.
#
# Asserts the exact header set on BOTH surfaces the include file exists to
# cover: `/` (the SPA shell) and the hashed bundle under `/assets/`. The second
# is not redundant — `location /assets/` declares its own `add_header`, which
# cancels every server-level header unless the include is repeated inside it.
# That exact regression already shipped once (see nginx-security-headers.conf).
#
#   ./scripts/spa-security-headers-gate.sh
#   WEB_URL=http://localhost:8080 ./scripts/spa-security-headers-gate.sh
#
# Exit 0 = every asserted header matched EXACTLY on both surfaces.
# Exit 1 = at least one did not.
# =============================================================================
set -uo pipefail

WEB_URL="${WEB_URL:-http://localhost:8080}"
WEB_URL="${WEB_URL%/}"
API_BASE_URL="${VITE_API_BASE_URL:-http://localhost:8000/api/v1}"

# The bundle can only reach the origin Vite inlined at build time, so the
# expected `connect-src` source is derived from the same variable the image was
# built with — the header and the bundle cannot drift apart. A relative base URL
# is same-origin and contributes no extra source.
API_ORIGIN="$(printf '%s' "$API_BASE_URL" | sed -n 's#^\([A-Za-z][A-Za-z0-9+.-]*://[^/]*\).*#\1#p')"

EXPECTED_CSP="default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self' ${API_ORIGIN}; base-uri 'none'; form-action 'self'; frame-ancestors 'none'; object-src 'none'"

# name|exact expected value. Header names are compared case-insensitively (HTTP
# field names are case-insensitive); values are compared byte for byte.
EXPECTED_HEADERS=(
  "content-security-policy|${EXPECTED_CSP}"
  "x-content-type-options|nosniff"
  "x-frame-options|DENY"
  "referrer-policy|strict-origin-when-cross-origin"
  "permissions-policy|camera=(), microphone=(), geolocation=(), payment=(), usb=()"
)

FAIL=0
say()  { printf '%s\n' "$*"; }
pass() { say "  PASS  $*"; }
fail() { say "  FAIL  $*"; FAIL=1; }

# Value of header $2 (lowercase name) from the raw header dump in file $1.
header_of() {
  local line name lname value
  while IFS= read -r line; do
    line="${line%$'\r'}"
    name="${line%%:*}"
    [ "$line" = "$name" ] && continue
    lname="$(printf '%s' "$name" | tr '[:upper:]' '[:lower:]')"
    if [ "$lname" = "$2" ]; then
      value="${line#*:}"
      printf '%s' "${value# }"
      return 0
    fi
  done < "$1"
  return 1
}

assert_surface() {
  local label="$1" url="$2" dump code entry name expected actual
  dump="$(mktemp)"
  code="$(curl -s -o /dev/null -D "$dump" -w '%{http_code}' --max-time 10 "$url" 2>/dev/null)"
  if [ "$code" != "200" ]; then
    fail "$label ($url) -> HTTP ${code:-no response}; cannot assert its headers"
    rm -f "$dump"
    return
  fi
  for entry in "${EXPECTED_HEADERS[@]}"; do
    name="${entry%%|*}"
    expected="${entry#*|}"
    if ! actual="$(header_of "$dump" "$name")"; then
      fail "$label: $name is ABSENT"
      continue
    fi
    if [ "$actual" = "$expected" ]; then
      pass "$label: $name"
    else
      fail "$label: $name"
      say "        expected: $expected"
      say "        actual:   $actual"
    fi
  done
  rm -f "$dump"
}

say "== SPA origin security headers ($WEB_URL) =="
say "   expected connect-src API origin: ${API_ORIGIN:-<same-origin only>}"

assert_surface "/" "$WEB_URL/"

# The hashed bundle is discovered from the shell rather than hard-coded: its
# name changes on every build, and a stale literal would silently degrade this
# into a second check of `/`.
ASSET_PATH="$(curl -fsS --max-time 10 "$WEB_URL/" 2>/dev/null \
  | sed -n 's#.*<script[^>]*src="\([^"]*\)".*#\1#p' | head -n1)"
if [ -z "$ASSET_PATH" ]; then
  fail "no <script src> found in the served index.html — cannot locate the bundle"
else
  assert_surface "$ASSET_PATH" "$WEB_URL$ASSET_PATH"
fi

say ""
if [ "$FAIL" = "0" ]; then
  say "SPA SECURITY HEADERS OK — CSP and the four companion headers ride both the shell and the bundle."
else
  say "SPA SECURITY HEADERS FAILED — fix the FAIL lines above."
fi
exit "$FAIL"
