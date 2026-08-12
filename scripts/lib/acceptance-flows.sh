#!/usr/bin/env bash
# =============================================================================
# Entropia — the FIVE acceptance flows (RC readiness §6.2 blocker 2).
#
# Sourced by scripts/e2e-acceptance.sh; driven by its `flows` subcommand. It is
# NOT a second harness: it reuses that script's isolation contract, hermetic
# env file, compose wrapper (`dc`), HTTP helpers (`req`/`has`/`jfield`) and its
# PASS/FAIL accounting verbatim. Nothing here brings up a stack of its own.
#
#   (a) Strategy -> Ready-check -> Run -> Result
#   (b) Library validation
#   (c) ESP lifecycle + export
#   (d) Agent Strategy / Trading Signal tools
#   (e) Trash: soft-delete -> restore -> purge
#
# TWO LAYERS, NEITHER ALLOWED TO STAND IN FOR THE OTHER
#   * Browser layer — the journeys frontend/e2e/specs/* ALREADY implement are
#     RUN, not reimplemented (05+18 = flow a, 20-library = flow b, 06 = flow e's
#     delete->purge leg). Rewriting them in curl would have produced a second,
#     weaker copy of a suite that is already a CI gate.
#   * Server layer — everything no layer covered: ESP lifecycle, package export
#     envelope, Trading Signal / Agent tool surfaces, and the Trash RESTORE leg
#     spec 06 skips. Plus the four invariants below, which a browser cannot
#     prove because a browser only ever sees what the UI chose to render.
#
# THE FOUR NON-NEGOTIABLES, ASSERTED NOT ASSUMED
#   1. Trading Signal / Trade Log are NOT Packages — different root, different
#      surface, absent from the Library catalog.
#   2. Backtest Run != Backtest Result — only a SUCCEEDED run yields a Result;
#      a rejected admission yields none.
#   3. UI hidden/disabled is NOT authorization — every Admin-gated surface is
#      re-attacked with a plain USER token and must answer 403 server-side.
#   4. Long work runs on the durable queue — admissions are 202 + a job id and
#      are followed through the worker, never short-circuited synchronously.
#
# HONESTY RULE: a flow that cannot run is recorded SKIP (its own counter, never
# folded into PASS). This file has no path that reports green for work it did
# not do.
# =============================================================================

AF_SKIP_N=0
af_skip() { AF_SKIP_N=$((AF_SKIP_N + 1)); printf '  \033[33mSKIP\033[0m  %s\n' "$*"; }

# Unique Idempotency-Key per call site — a retried submit must not write twice.
AF_KEY_SEQ=0
af_key() { AF_KEY_SEQ=$((AF_KEY_SEQ + 1)); printf 'af-%s-%s-%s' "${1:-op}" "$$" "$AF_KEY_SEQ"; }

# First integer value of "FIELD": N (jfield only reads quoted strings).
af_int() { printf '%s' "$1" | sed -n 's/.*"'"$2"'"[[:space:]]*:[[:space:]]*\([0-9][0-9]*\).*/\1/p' | head -n1; }
# Truncated body, safe to print on a FAIL line.
af_peek() { printf '%s' "${1:0:400}"; }

AF_ADMIN_TOK=""; AF_USER_TOK=""; AF_ADMIN_ID=""; AF_WORKSPACE=""
AF_ADMIN_USER="af_admin"; AF_ADMIN_PW="Af-Admin-Passw0rd!23"
AF_PLAIN_USER="af_user";  AF_PLAIN_PW="Af-Member-Passw0rd!23"

# --- shared bootstrap --------------------------------------------------------
# One Admin (bootstrap email auto-promotes the first signup) and one plain USER.
# The USER exists for exactly one purpose: to prove non-negotiable 3 on every
# Admin-gated route. Without a second principal "Admin can do it" is the only
# thing any assertion here could show.
af_bootstrap_actors() {
  step "[flows/0] bootstrap the two principals every flow needs (Admin + plain USER)"

  req POST /auth/signup -H 'Content-Type: application/json' \
    -d "{\"username\":\"$AF_ADMIN_USER\",\"password\":\"$AF_ADMIN_PW\",\"email\":\"$BOOTSTRAP_EMAIL\"}"
  AF_ADMIN_ID="$(jfield "$LAST_BODY" user_id)"
  req POST /auth/login -H 'Content-Type: application/json' \
    -d "{\"username\":\"$AF_ADMIN_USER\",\"password\":\"$AF_ADMIN_PW\"}"
  AF_ADMIN_TOK="$(jfield "$LAST_BODY" token)"
  req GET /me -H "Authorization: Bearer $AF_ADMIN_TOK"
  { [ -n "$AF_ADMIN_TOK" ] && has "$LAST_BODY" '"is_admin":true'; } \
    && ok "[0] Admin principal authenticated (is_admin=true)" \
    || { bad "[0] no Admin session -> $LAST_STATUS $(af_peek "$LAST_BODY")"; return 1; }

  req POST /auth/signup -H 'Content-Type: application/json' \
    -d "{\"username\":\"$AF_PLAIN_USER\",\"password\":\"$AF_PLAIN_PW\",\"email\":\"af-member@entropia.local\"}"
  req POST /auth/login -H 'Content-Type: application/json' \
    -d "{\"username\":\"$AF_PLAIN_USER\",\"password\":\"$AF_PLAIN_PW\"}"
  AF_USER_TOK="$(jfield "$LAST_BODY" token)"
  req GET /me -H "Authorization: Bearer $AF_USER_TOK"
  { [ -n "$AF_USER_TOK" ] && has "$LAST_BODY" '"is_admin":false'; } \
    && ok "[0] plain USER principal authenticated (is_admin=false)" \
    || { bad "[0] no USER session -> $LAST_STATUS $(af_peek "$LAST_BODY")"; return 1; }

  # compositionId IS workspace_id on this API (frontend/src/pages/Mainboard.tsx:1241).
  req GET /mainboards/default -H "Authorization: Bearer $AF_ADMIN_TOK"
  AF_WORKSPACE="$(jfield "$LAST_BODY" workspace_id)"
  [ -n "$AF_WORKSPACE" ] \
    && ok "[0] default mainboard composition resolved ($AF_WORKSPACE)" \
    || bad "[0] GET /mainboards/default -> $LAST_STATUS $(af_peek "$LAST_BODY")"
}

# =============================================================================
# (a) Strategy -> Ready-check -> Run -> Result
# =============================================================================
# The POSITIVE golden path is spec 05 (browser layer) — it builds the strategy
# through the real typed forms, gets an explicit Ready, watches RUN flip
# disabled->enabled and follows the run to SUCCEEDED with an inline immutable
# Result. Reimplementing that in curl would duplicate a CI-gated journey badly.
#
# What NO layer covered, and what this asserts, is the NEGATIVE half — which is
# where non-negotiable 2 actually lives. "Only a SUCCEEDED run produces a
# Result" is only meaningful if a non-succeeding run demonstrably produces
# none, and a green golden path can never show that.
af_flow_a_strategy_run() {
  banner "(a) STRATEGY -> READY-CHECK -> RUN -> RESULT"
  local tokA="$AF_ADMIN_TOK" comp="$AF_WORKSPACE"

  step "[a1] the composition's readiness projection is server-computed"
  req GET "/mainboard-compositions/$comp/readiness" -H "Authorization: Bearer $tokA"
  { [ "$LAST_STATUS" = 200 ] && has "$LAST_BODY" '"state"'; } \
    && ok "[a1] GET .../readiness -> 200, state=$(jfield "$LAST_BODY" state) (the client never computes this)" \
    || bad "[a1] readiness -> $LAST_STATUS $(af_peek "$LAST_BODY")"
  # Before the first check the projection carries no fingerprint (state
  # not_checked, report_id null) — the OCC token for the FIRST Ready Check comes
  # from the composition itself, which is where the UI reads it too.
  local fp; fp="$(jfield "$LAST_BODY" current_fingerprint)"
  if [ -z "$fp" ]; then
    req GET /mainboards/default -H "Authorization: Bearer $tokA"
    fp="$(jfield "$LAST_BODY" composition_hash)"
  fi

  step "[a2] Ready Check is a real evaluation, and a STALE fingerprint creates NOTHING"
  req POST "/mainboard-compositions/$comp/readiness-checks" -H "Authorization: Bearer $tokA" \
    -H 'Content-Type: application/json' -d '{"expected_fingerprint":"sha256:deliberately-stale"}'
  { [ "$LAST_STATUS" != 200 ] && [ "$LAST_STATUS" != 201 ]; } \
    && ok "[a2] stale expected_fingerprint -> $LAST_STATUS (no report minted on a stale composition)" \
    || bad "[a2] stale fingerprint was ACCEPTED -> $LAST_STATUS (OCC not enforced)"

  local report_id="" state=""
  if [ -n "$fp" ]; then
    req POST "/mainboard-compositions/$comp/readiness-checks" -H "Authorization: Bearer $tokA" \
      -H 'Content-Type: application/json' -H "Idempotency-Key: $(af_key rc)" \
      -d "{\"expected_fingerprint\":\"$fp\"}"
    report_id="$(jfield "$LAST_BODY" report_id)"; state="$(jfield "$LAST_BODY" state)"
    { [ "$LAST_STATUS" = 201 ] || [ "$LAST_STATUS" = 200 ]; } \
      && ok "[a2] current fingerprint -> $LAST_STATUS, immutable report minted (state=$state)" \
      || bad "[a2] readiness-check -> $LAST_STATUS $(af_peek "$LAST_BODY")"
  else
    # Measured, not assumed: on the bootstrap composition `composition_hash` is
    # null and readiness is `not_checked`. An empty composition has nothing to
    # fingerprint, so no Ready Check can be minted for it and RUN therefore stays
    # locked ([a3] below shows the refusal). The POSITIVE path — a populated
    # composition returning an explicit Ready and flipping RUN disabled->enabled —
    # needs a real strategy built through the typed forms, which is exactly what
    # the browser layer runs at the end of this file (spec 05).
    ok "[a2] empty composition has no fingerprint (composition_hash null, state not_checked) — nothing to certify, so nothing is certified"
    info "[a2] the positive Ready->RUN transition is asserted by specs/05-mainboard-ready-check-run.spec.ts, run below against this same stack"
  fi

  step "[a3] NON-NEGOTIABLE 2 — Backtest Run != Backtest Result"
  # An empty default composition is NOT ready. The admission must be refused,
  # and refusing it must leave the Results plane untouched: a Result is a
  # by-product of a SUCCEEDED run, never of a request to run.
  local before after
  req GET /backtest-results -H "Authorization: Bearer $tokA"
  before="$(printf '%s' "$LAST_BODY" | grep -o '"result_id"' | wc -l | tr -d '[:space:]')"
  req POST "/mainboard-compositions/$comp/backtest-runs" -H "Authorization: Bearer $tokA" \
    -H 'Content-Type: application/json' -H "Idempotency-Key: $(af_key run)" \
    -d "{\"expected_fingerprint\":\"${fp:-sha256:none}\",\"ready_report_id\":\"${report_id:-rep_none}\"}"
  local run_status="$LAST_STATUS" run_body="$LAST_BODY"
  req GET /backtest-results -H "Authorization: Bearer $tokA"
  after="$(printf '%s' "$LAST_BODY" | grep -o '"result_id"' | wc -l | tr -d '[:space:]')"

  if [ "$run_status" = 202 ]; then
    # Admitted: then non-negotiable 4 applies — follow the DURABLE path, and a
    # Result may only appear once the run actually reaches SUCCEEDED.
    local run_id; run_id="$(jfield "$run_body" run_id)"
    ok "[a3] run admitted 202 (run_id=$run_id) — admission is an ACCEPT, not a Result"
    af_follow_run "$run_id" "$tokA"
  else
    [ "${after:-0}" = "${before:-0}" ] \
      && ok "[a3] run refused ($run_status) on a not-ready composition and minted NO Result (results $before -> $after)" \
      || bad "[a3] a refused run changed the Results plane: $before -> $after"
    has "$run_body" '"code"' \
      && ok "[a3] refusal answers the canonical ErrorBody envelope, not a bare failure" \
      || bad "[a3] refusal body is not an ErrorBody -> $(af_peek "$run_body")"
    # O-02: a readiness blocker promotes the leading blocker's remediation.
    has "$run_body" 'remediation' \
      && ok "[a3] refusal carries the recovery block (remediation surfaced to the caller)" \
      || info "[a3] refusal envelope carried no remediation key (recorded, not asserted green)"
  fi

  step "[a4] NON-NEGOTIABLE 3 — the plain USER is refused SERVER-SIDE, not by a hidden button"
  req POST "/mainboard-compositions/$comp/backtest-runs" -H "Authorization: Bearer $AF_USER_TOK" \
    -H 'Content-Type: application/json' -d "{\"expected_fingerprint\":\"${fp:-x}\"}"
  { [ "$LAST_STATUS" = 403 ] || [ "$LAST_STATUS" = 404 ]; } \
    && ok "[a4] USER -> POST backtest-runs on another principal's composition = $LAST_STATUS" \
    || bad "[a4] USER reached another principal's run admission -> $LAST_STATUS $(af_peek "$LAST_BODY")"
}

# Follow an admitted run through the REAL worker to a terminal state, then hold
# the Run/Result distinction to it. No synchronous shortcut exists here: the
# only way this returns is the durable job actually moving.
af_follow_run() {
  local run_id="$1" tok="$2" i term=""
  for i in $(seq 1 90); do
    req GET "/backtest-runs/$run_id" -H "Authorization: Bearer $tok"
    term="$(jfield "$LAST_BODY" status)"
    case "$term" in SUCCEEDED|FAILED|CANCELLED|REJECTED|succeeded|failed|cancelled|rejected) break ;; esac
    sleep 2
  done
  local result_id; result_id="$(jfield "$LAST_BODY" result_id)"
  case "$term" in
    SUCCEEDED|succeeded)
      [ -n "$result_id" ] \
        && ok "[a3] run reached SUCCEEDED on the durable worker and produced ONE immutable Result ($result_id)" \
        || bad "[a3] run SUCCEEDED but no Result was materialised" ;;
    "")
      bad "[a3] run $run_id never reached a terminal state within 180s (durable path stalled)" ;;
    *)
      [ -z "$result_id" ] \
        && ok "[a3] run terminated $term and produced NO Result — Run != Result holds" \
        || bad "[a3] a $term run produced a Result ($result_id)" ;;
  esac
}

# =============================================================================
# (b) Library validation
# =============================================================================
# Browser layer: spec 20-library-request-validation drives draft -> Library
# detail -> Request Validation -> durable worker -> PASSED -> approval unlocked.
# Server layer below adds the half a browser cannot see: that the Library's
# Admin/owner actions are refused to a plain USER by the SERVER, and that the
# head-match precondition refuses a mismatched head instead of racing it.
af_flow_b_library_validation() {
  banner "(b) LIBRARY VALIDATION"
  local tokA="$AF_ADMIN_TOK" pkg=""

  step "[b1] the seeded, published package is served by the Library catalog"
  req GET /library -H "Authorization: Bearer $tokA"
  pkg="$(jfield "$LAST_BODY" entity_id)"
  { [ "$LAST_STATUS" = 200 ] && [ -n "$pkg" ]; } \
    && ok "[b1] GET /library -> 200, package root $pkg present (SEED_E2E_GOLDEN/SEED_ESP_TA)" \
    || { bad "[b1] GET /library -> $LAST_STATUS $(af_peek "$LAST_BODY")"; return; }

  req GET "/library/$pkg" -H "Authorization: Bearer $tokA"
  # queries/library.py:520 projects the head as `revision_id`, not
  # `head_revision_id` — the latter is the OCC *token* name, not a body field.
  local head; head="$(jfield "$LAST_BODY" revision_id)"
  { [ "$LAST_STATUS" = 200 ] && [ -n "$head" ]; } \
    && ok "[b1] GET /library/$pkg -> 200 (head revision $head)" \
    || bad "[b1] package detail -> $LAST_STATUS $(af_peek "$LAST_BODY")"

  step "[b2] validation is head-matched — a mismatched head is refused, never raced"
  req POST "/library/$pkg/validation-runs" -H "Authorization: Bearer $tokA" \
    -H 'Content-Type: application/json' -H "Idempotency-Key: $(af_key val)" \
    -d '{"expected_head_revision_id":"rev_deliberately_wrong"}'
  { [ "$LAST_STATUS" != 200 ] && [ "$LAST_STATUS" != 201 ]; } \
    && ok "[b2] mismatched expected_head_revision_id -> $LAST_STATUS (precondition refused)" \
    || bad "[b2] a mismatched head was ACCEPTED -> $LAST_STATUS"

  step "[b3] NON-NEGOTIABLE 3 — Library lifecycle actions are gated on the SERVER"
  # The body must be WELL FORMED or pydantic answers 422 before the authorization
  # gate is ever consulted, and a 422 would prove nothing about who may approve.
  # (First run made exactly that mistake: `revision_id` is required.)
  req POST "/library/$pkg/approve" -H "Authorization: Bearer $AF_USER_TOK" \
    -H 'Content-Type: application/json' \
    -d "{\"revision_id\":\"${head:-x}\",\"expected_head_revision_id\":\"${head:-x}\"}"
  { [ "$LAST_STATUS" = 403 ] || [ "$LAST_STATUS" = 404 ]; } \
    && ok "[b3] USER -> POST /library/$pkg/approve = $LAST_STATUS (not a hidden button)" \
    || bad "[b3] USER reached package approval -> $LAST_STATUS $(af_peek "$LAST_BODY")"
  req DELETE "/library/$pkg" -H "Authorization: Bearer $AF_USER_TOK" -H 'If-Match: rv-1'
  { [ "$LAST_STATUS" = 403 ] || [ "$LAST_STATUS" = 404 ]; } \
    && ok "[b3] USER -> DELETE /library/$pkg = $LAST_STATUS" \
    || bad "[b3] USER reached package soft-delete -> $LAST_STATUS"
  AF_PKG_ID="$pkg"; AF_PKG_HEAD="$head"
}

# =============================================================================
# (c) ESP lifecycle + export
# =============================================================================
# NO layer covered this at the acceptance level before (backend/tests/contract +
# integration exercise it in-process; frontend/e2e only reads the registry page
# in spec 17). Resolver activation is the highest-trust mutation in the product
# — it changes what every strategy in the system resolves to — so it gets the
# full treatment: registry OCC, Admin gating on the server, and an export
# envelope that must actually carry its provenance.
af_flow_c_esp_lifecycle_export() {
  banner "(c) ESP LIFECYCLE + EXPORT"
  local tokA="$AF_ADMIN_TOK"
  local key="af.probe.rc.v1"
  local sig='{"params":[{"name":"arg0","type":"series"}],"return":"series"}'
  # WELL-FORMED, EXECUTABLE-SHAPED test vectors (ADIM 45). The first run of this
  # flow sent `"test_vectors":"rc-harness"` — a STRING, which
  # domain/esp/validation.py::_extract_vectors drops, so the run measured
  # vectors_run=0 and the SKIP in [c5] could be misread as "the harness was too
  # lazy to supply vectors". It now supplies real ones, in the exact shape
  # ``_run_one_vector`` executes (length / close / expected, null = warm-up), so
  # vectors_run is non-zero and the refusal in [c5] can only be about
  # EXECUTABILITY of the key, never about absence of evidence.
  # A CONSTANT close series is deliberate: every MA variant (sma/ema/rma/wma)
  # returns the constant after its `length`-bar warm-up, so this expectation is
  # implementation-independent and cannot silently encode one variant's math.
  local vectors='[{"name":"constant-window-3","length":3,"close":[100,100,100,100,100],"expected":[null,null,100,100,100]},{"name":"constant-window-2","length":2,"close":[7,7,7],"expected":[null,7,7]}]'

  step "[c1] create an Embedded System Package (resolver contract)"
  req POST /embedded-system-packages -H "Authorization: Bearer $tokA" \
    -H 'Content-Type: application/json' -H "Idempotency-Key: $(af_key esp)" \
    -d "{\"canonical_key\":\"$key\",\"runtime_adapter\":\"python\",\"signature\":$sig,\"input_contract\":{\"resolver_key\":\"$key\",\"signature\":$sig},\"output_contract\":{\"return\":\"series\"},\"timing_semantics\":\"closed_bar_only\",\"repaint\":false,\"evidence\":{\"test_vectors\":$vectors,\"review\":\"passed\"},\"change_note\":\"RC acceptance harness probe resolver.\"}"
  local esp_id esp_rev
  esp_id="$(jfield "$LAST_BODY" entity_id)"; esp_rev="$(jfield "$LAST_BODY" revision_id)"
  { [ "$LAST_STATUS" = 201 ] && [ -n "$esp_id" ] && [ -n "$esp_rev" ]; } \
    && ok "[c1] POST /embedded-system-packages -> 201 ($esp_id / $esp_rev, trust=$(jfield "$LAST_BODY" trust_state))" \
    || { bad "[c1] ESP create -> $LAST_STATUS $(af_peek "$LAST_BODY")"; return; }

  step "[c2] resolver validation runs the declared test vectors — and FAILS CLOSED on an unknown key"
  req POST "/embedded-system-packages/$esp_id/validate" -H "Authorization: Bearer $tokA" \
    -H 'Content-Type: application/json' -H "Idempotency-Key: $(af_key espval)" \
    -d "{\"revision_id\":\"$esp_rev\"}"
  local vstate vran; vstate="$(jfield "$LAST_BODY" validation_state)"; vran="$(af_int "$LAST_BODY" vectors_run)"
  [ "$LAST_STATUS" = 200 ] \
    && ok "[c2] validate -> 200 (state=$vstate, vectors_run=$vran)" \
    || bad "[c2] validate -> $LAST_STATUS $(af_peek "$LAST_BODY")"
  # The vectors ARE present and well-formed now, so a zero here would mean the
  # payload regressed back to the string form — not a product fact.
  [ "${vran:-0}" -gt 0 ] \
    && ok "[c2] the declared vectors were parsed as executable vectors (vectors_run=$vran, not the dropped-string 0)" \
    || bad "[c2] vectors_run=$vran — the harness's own evidence payload is malformed, nothing about the product was measured"
  # PINNED, and pinned deliberately (ADIM 45). `af.probe.rc.v1` is not in
  # domain/backtest/indicators.py::VALIDATABLE_RESOLVER_KEYS, so doc 09 §7's
  # fail-closed rule must refuse it EVEN THOUGH its evidence is now complete:
  # "No executable compute for '<key>'". If this ever reads `passed`, an
  # arbitrary caller-named key became certifiable — that is a product change
  # that must go red here and force the [c5] adjudication to be reopened, not
  # slide through as a quietly-improved harness.
  [ "$vstate" = "failed" ] \
    && ok "[c2] fail-closed holds: complete evidence + an unlisted canonical key -> validation_state=failed (doc 09 §7)" \
    || bad "[c2] validation_state='$vstate' for an unlisted key (want 'failed') — the fail-closed rule moved; reopen the [c5] adjudication"

  step "[c3] NON-NEGOTIABLE 3 — activation is Admin-only ON THE SERVER"
  req POST "/embedded-system-packages/$esp_id/activate" -H "Authorization: Bearer $AF_USER_TOK" \
    -H 'Content-Type: application/json' -H 'X-Registry-Version: 0' \
    -d "{\"canonical_key\":\"$key\",\"revision_id\":\"$esp_rev\"}"
  { [ "$LAST_STATUS" = 403 ] || [ "$LAST_STATUS" = 404 ]; } \
    && ok "[c3] USER -> activate = $LAST_STATUS (the registry cannot be moved by a hidden-button bypass)" \
    || bad "[c3] USER activated a resolver -> $LAST_STATUS $(af_peek "$LAST_BODY")"

  step "[c4] the registry version is a real OCC token — a stale one is refused"
  req POST "/embedded-system-packages/$esp_id/activate" -H "Authorization: Bearer $tokA" \
    -H 'Content-Type: application/json' -H 'X-Registry-Version: 999999' \
    -d "{\"canonical_key\":\"$key\",\"revision_id\":\"$esp_rev\"}"
  { [ "$LAST_STATUS" != 200 ] && [ "$LAST_STATUS" != 201 ]; } \
    && ok "[c4] stale X-Registry-Version 999999 -> $LAST_STATUS (activation refused)" \
    || bad "[c4] a stale registry version ACTIVATED a resolver -> $LAST_STATUS"

  step "[c5] a resolver whose validation FAILED cannot be promoted to trusted-active"
  # [c2] measured validation_state=failed with COMPLETE evidence (vectors_run>0).
  # That is the interesting case: the registry gate must refuse it for a TRUST
  # reason, not merely bounce it on the version token. So walk the token until the
  # answer stops being a version conflict, and read what the server says at the
  # CORRECT version.
  local v verdict="" vstatus="" vcode=""
  for v in 0 1 2 3; do
    req POST "/embedded-system-packages/$esp_id/activate" -H "Authorization: Bearer $tokA" \
      -H 'Content-Type: application/json' -H "X-Registry-Version: $v" -H "Idempotency-Key: $(af_key act$v)" \
      -d "{\"canonical_key\":\"$key\",\"revision_id\":\"$esp_rev\",\"note\":\"RC acceptance harness\"}"
    vstatus="$LAST_STATUS"; vcode="$(jfield "$LAST_BODY" code)"
    if [ "$vstatus" = 200 ] || [ "$vcode" != "RESOLVER_REGISTRY_CONFLICT" ]; then verdict="$v"; break; fi
  done

  if [ "$vstatus" = 200 ]; then
    local nextv; nextv="$(af_int "$LAST_BODY" registry_version)"
    ok "[c5] activate -> 200 at X-Registry-Version=$verdict; trust=$(jfield "$LAST_BODY" trust_state), next token=$nextv"
    req POST "/embedded-system-packages/$esp_id/deprecate" -H "Authorization: Bearer $tokA" \
      -H 'Content-Type: application/json' -H "X-Registry-Version: ${nextv:-1}" -H "Idempotency-Key: $(af_key dep)" \
      -d "{\"canonical_key\":\"$key\",\"reason\":\"RC acceptance harness teardown\"}"
    [ "$LAST_STATUS" = 200 ] \
      && ok "[c5] deprecate -> 200 (trust=$(jfield "$LAST_BODY" trust_state))" \
      || bad "[c5] deprecate -> $LAST_STATUS $(af_peek "$LAST_BODY")"
  elif [ -n "$verdict" ]; then
    ok "[c5] at the current registry version the promotion is refused $vstatus $vcode — an UNVALIDATED resolver cannot become trusted-active"
    # PINNED: the refusal must be the VALIDATION gate, not the evidence-presence
    # gate that runs before it (commands/esp.py::_ensure_validation_passed calls
    # _ensure_activation_evidence FIRST). Before ADIM 45 the evidence payload was
    # a string, so this could just as well have been RESOLVER_EVIDENCE_REQUIRED
    # and nobody would have noticed the difference — asserting only "not 200"
    # could not tell the two gates apart.
    { [ "$vstatus" = 409 ] && [ "$vcode" = "RESOLVER_VALIDATION_REQUIRED" ]; } \
      && ok "[c5] the refusal is the VALIDATION gate (409 RESOLVER_VALIDATION_REQUIRED), not the evidence-presence gate" \
      || bad "[c5] refusal was $vstatus $vcode — want 409 RESOLVER_VALIDATION_REQUIRED (evidence is complete, so RESOLVER_EVIDENCE_REQUIRED here would mean the gate order changed)"
    # ADJUDICATED (ADIM 45) — this SKIP is STRUCTURAL, not laziness. The recorded
    # reason used to be "the harness does not synthesise test vectors"; that was
    # only half true and is now fixed (vectors are supplied, [c2] proves they
    # parse). The real reason the positive activate->deprecate leg cannot run in
    # THIS stack is a three-way lock between shipped invariants:
    #   1. validation can only PASS for the six canonical keys in
    #      indicators.py::VALIDATABLE_RESOLVER_KEYS (ta.sma/ema/rma/wma/rsi/vwap)
    #      — everything else fails closed by design (doc 09 §7);
    #   2. apps/seed.py::_ESP_TA_RESOLVERS seeds ALL SIX as trusted_active,
    #      because the browser layer's Pre-Check needs them resolvable;
    #   3. esp/state_machine.py::_ALLOWED permits activation ONLY from
    #      `candidate` (and `deprecated` is terminal apart from `unavailable`),
    #      so a key that is already trusted_active can never be re-activated.
    # So on a SEED_ESP_TA stack there is NO key that is both validatable and
    # activatable, and no ordering of harness calls creates one. Closing it would
    # need either a second Compose stack seeded without SEED_ESP_TA (a whole new
    # 12-container CI job for one assertion) or a change to seed.py — product
    # code, out of scope for a CI-wiring slice. The positive leg keeps its
    # in-process coverage: backend/tests/integration/test_esp_persistence.py.
    af_skip "[c5] positive activate->deprecate NOT driven here — structural: no canonical key is both validatable (VALIDATABLE_RESOLVER_KEYS) and activatable (seeded trusted_active + activation legal only from candidate). See the block above; in-process coverage: backend/tests/integration/test_esp_persistence.py"
  else
    bad "[c5] every registry version 0..3 answered RESOLVER_REGISTRY_CONFLICT -> $(af_peek "$LAST_BODY")"
  fi

  step "[c5b] the registry does reach trusted-active — the seeded canonical resolvers prove it"
  req GET /embedded-system-packages -H "Authorization: Bearer $tokA"
  { [ "$LAST_STATUS" = 200 ] && has "$LAST_BODY" 'trusted_active'; } \
    && ok "[c5b] GET /embedded-system-packages lists a trusted_active entry (SEED_ESP_TA)" \
    || bad "[c5b] no trusted_active resolver in the registry -> $LAST_STATUS $(af_peek "$LAST_BODY")"

  step "[c6] package EXPORT carries its provenance envelope (G-02 schema v2 / G-05)"
  if [ -z "${AF_PKG_ID:-}" ]; then af_skip "[c6] no Library package resolved in (b)"; return; fi
  req GET "/library/$AF_PKG_ID" -H "Authorization: Bearer $tokA"
  local exrev; exrev="$(jfield "$LAST_BODY" head_revision_id)"
  [ -z "$exrev" ] && exrev="$(jfield "$LAST_BODY" revision_id)"
  req POST "/library/$AF_PKG_ID/export" -H "Authorization: Bearer $tokA" \
    -H 'Content-Type: application/json' -H "Idempotency-Key: $(af_key exp)" \
    -d "{\"revision_id\":\"$exrev\"}"
  if [ "$LAST_STATUS" = 200 ] || [ "$LAST_STATUS" = 201 ]; then
    ok "[c6] POST /library/$AF_PKG_ID/export -> $LAST_STATUS"
    has "$LAST_BODY" '"export_schema_version"' \
      && ok "[c6] manifest declares export_schema_version (an importer can refuse an unknown one)" \
      || bad "[c6] export omitted export_schema_version"
    has "$LAST_BODY" '"manifest_hash"' \
      && ok "[c6] export is content-addressed (manifest_hash present)" || bad "[c6] no manifest_hash"
    has "$LAST_BODY" '"registry_observation"' \
      && ok "[c6] the LIVE registry pointer travels beside the manifest, not inside it (G-05)" \
      || bad "[c6] registry_observation absent — export provenance incomplete"
  else
    bad "[c6] export -> $LAST_STATUS $(af_peek "$LAST_BODY")"
  fi
}

# =============================================================================
# (d) Agent Strategy / Trading Signal tools
# =============================================================================
# Also previously uncovered at the acceptance level. Non-negotiable 1 lives
# here: Trading Signal and Trade Log are twin surfaces of their OWN root type —
# calling them "packages" is the specific mistake this flow exists to catch.
af_flow_d_agent_signal_tools() {
  banner "(d) AGENT STRATEGY / TRADING SIGNAL TOOLS"
  local tokA="$AF_ADMIN_TOK"

  step "[d1] NON-NEGOTIABLE 1 — a Trading Signal is NOT a Package"
  req GET /library -H "Authorization: Bearer $tokA"
  { ! has "$LAST_BODY" '"trading_signal"' && ! has "$LAST_BODY" '"trade_log"'; } \
    && ok "[d1] the Library catalog contains no trading_signal / trade_log root (separate taxonomies)" \
    || bad "[d1] the Library catalog is carrying a signal/log root -> $(af_peek "$LAST_BODY")"
  if [ -n "${AF_PKG_ID:-}" ]; then
    req GET "/trading-signals/$AF_PKG_ID" -H "Authorization: Bearer $tokA"
    { [ "$LAST_STATUS" != 200 ]; } \
      && ok "[d1] a Package root is not addressable on the Trading Signal surface -> $LAST_STATUS" \
      || bad "[d1] GET /trading-signals/<package root> returned 200 — the two roots are being conflated"
  fi

  step "[d2] the upload file-type gate is FAIL-CLOSED (K-07)"
  local tmpd; tmpd="$(mktemp -d)"
  printf 'time,close\n2024-01-01T00:00:00Z,100\n' > "$tmpd/ok.csv"
  printf 'MZ binary payload\n' > "$tmpd/payload.exe"
  req POST /trading-signals/source-assets -H "Authorization: Bearer $tokA" \
    -F "file=@$tmpd/payload.exe;type=application/octet-stream"
  { [ "$LAST_STATUS" != 200 ] && [ "$LAST_STATUS" != 201 ]; } \
    && ok "[d2] a .exe upload is refused -> $LAST_STATUS $(jfield "$LAST_BODY" code)" \
    || bad "[d2] a .exe was ACCEPTED as a signal source asset -> $LAST_STATUS"
  # A missing/blank filename must be REFUSED, never waved through as "unknown".
  req POST /trading-signals/source-assets -H "Authorization: Bearer $tokA" \
    -F "file=@$tmpd/ok.csv;filename="
  { [ "$LAST_STATUS" != 200 ] && [ "$LAST_STATUS" != 201 ]; } \
    && ok "[d2] a blank filename is refused, not skipped -> $LAST_STATUS $(jfield "$LAST_BODY" code)" \
    || bad "[d2] a blank filename was accepted -> $LAST_STATUS (gate is fail-OPEN)"
  rm -rf "$tmpd"

  step "[d3] the Agent workspace read surfaces answer"
  req GET /agent-workspace/overview -H "Authorization: Bearer $tokA"
  [ "$LAST_STATUS" = 200 ] && ok "[d3] GET /agent-workspace/overview -> 200" || bad "[d3] overview -> $LAST_STATUS"
  # A freshly migrated database HAS the singleton runtime row (alembic 0016
  # bulk-inserts it ACTIVE) but NO tasks — so the queue is legitimately empty
  # here. The Tool Gateway call log is exercised in [d5], against the task the
  # Coordinator materialises from [d4]'s directive.
  req GET /agent-tasks -H "Authorization: Bearer $tokA"
  [ "$LAST_STATUS" = 200 ] && ok "[d3] GET /agent-tasks -> 200 (queue empty on a fresh stack)" || bad "[d3] agent-tasks -> $LAST_STATUS"

  step "[d4] NON-NEGOTIABLE 4 — a directive is a DURABLE admission, not a synchronous call"
  req POST /agent-directives -H "Authorization: Bearer $tokA" \
    -H 'Content-Type: application/json' -H "Idempotency-Key: $(af_key dir)" \
    -d '{"text":"RC acceptance harness directive — no side effect expected.","priority":"normal"}'
  [ "$LAST_STATUS" = 202 ] \
    && ok "[d4] POST /agent-directives -> 202 (queued for the coordinator, not executed inline)" \
    || bad "[d4] directive -> $LAST_STATUS $(af_peek "$LAST_BODY")"

  step "[d5] the Coordinator CONSUMES the directive and the Tool Gateway log is served for the task it spawns"
  # ADIM 45 — this closes the second SKIP the RC report §6.2 recorded ("Tool
  # Gateway call log not exercised — no agent task on a freshly seeded stack").
  # The fix was not to seed a task: a seeded row would have proved only that the
  # read endpoint can project a fixture. The task is now the REAL one
  # commands/agent_loop.py::_spawn_followup_task materialises when the
  # agent-coordinator plane consumes [d4]'s directive, so the same wait that
  # earns the tool-call assertion also upgrades non-negotiable 4 from "the
  # admission was ACCEPTED" to "the admission was CONSUMED by the durable
  # plane". A 202 that nothing ever picks up is exactly the silent failure that
  # rule exists to catch, and until now nothing here would have noticed it.
  # Budget: apps/agent_coordinator/__main__.py::CYCLE_SLEEP_SECONDS is 10, so
  # 90s is nine cycles — generous, and still bounded.
  local task_id="" i
  for i in $(seq 1 18); do
    req GET /agent-tasks -H "Authorization: Bearer $tokA"
    task_id="$(jfield "$LAST_BODY" task_id)"
    [ -n "$task_id" ] && break
    sleep 5
  done
  # NOT `bad ...; return` (the idiom used in [b1]/[e1]/[e3]): a stalled
  # Coordinator says nothing about whether the runtime controls in [d6] are
  # role-gated, and returning here would silently drop that assertion on the
  # very run where the agent plane is already misbehaving. One failure, one
  # FAIL line, and the rest of the flow still gets measured.
  if [ -z "$task_id" ]; then
    bad "[d5] no agent task appeared within 90s — the directive was accepted (202) but the Coordinator never consumed it (durable plane stalled)"
  else
    ok "[d5] the Coordinator materialised task $task_id from the directive — the 202 was consumed, not merely accepted"
    has "$LAST_BODY" '"source":"directive"' \
      && ok "[d5] the task's provenance is source=directive (queries/agent_workspace.py::_task_card)" \
      || bad "[d5] task $task_id does not carry source=directive -> $(af_peek "$LAST_BODY")"
    req GET "/agent-tasks/$task_id/tool-calls" -H "Authorization: Bearer $tokA"
    # The envelope is `{"tool_calls": [...]}` with NO count field — schemas/
    # agent_tool_gateway.py::AgentToolCallListResponse deliberately advertises no
    # `meta`/cursor it never advances — so the log depth is counted the same way
    # flow (a) counts results, off the card id.
    local calls; calls="$(printf '%s' "$LAST_BODY" | grep -o '"tool_call_id"' | wc -l | tr -d '[:space:]')"
    { [ "$LAST_STATUS" = 200 ] && has "$LAST_BODY" '"tool_calls"'; } \
      && ok "[d5] Tool Gateway call log served for the REAL task $task_id (typed envelope, ${calls:-0} call(s) logged)" \
      || bad "[d5] tool-calls -> $LAST_STATUS $(af_peek "$LAST_BODY")"
    # The log is asserted as SERVED, not as non-empty: whether the executor has
    # dispatched a governed tool call by this point is a timing fact about the
    # executor plane, and claiming a count would make this assertion flaky rather
    # than stronger. The count is printed above so a regression to zero is visible.
    req GET "/agent-tasks/$task_id/tool-calls" -H "Authorization: Bearer $AF_USER_TOK"
    { [ "$LAST_STATUS" = 403 ] || [ "$LAST_STATUS" = 404 ]; } \
      && ok "[d5] NON-NEGOTIABLE 3 — USER -> GET the tool-call log = $LAST_STATUS" \
      || bad "[d5] USER read the Tool Gateway call log -> $LAST_STATUS"
  fi

  step "[d6] NON-NEGOTIABLE 3 — agent runtime controls are role-gated ON THE SERVER"
  # Renumbered from [d5] in ADIM 45 (the Coordinator/tool-call step took that
  # slot). Deliberately LAST in this flow: a successful pause would stop the
  # Coordinator, and [d5] above depends on it still cycling. The attempt is
  # expected to be refused, but ordering the flow so that a REGRESSION here
  # (a USER who really can pause) cannot also silently break [d5] keeps the two
  # failures readable as two failures.
  req POST /agent-runtime/pause -H "Authorization: Bearer $AF_USER_TOK" -H 'If-Match: 0'
  { [ "$LAST_STATUS" = 403 ] || [ "$LAST_STATUS" = 404 ]; } \
    && ok "[d6] USER -> POST /agent-runtime/pause = $LAST_STATUS" \
    || bad "[d6] USER reached the agent runtime control -> $LAST_STATUS $(af_peek "$LAST_BODY")"
}

# =============================================================================
# (e) Trash: soft-delete -> restore -> purge
# =============================================================================
# Browser layer: spec 06 drives soft-delete -> re-auth -> purge request. It
# SKIPS restore entirely, which is the leg that decides whether Trash is a
# recycle bin or a one-way shredder — so restore is asserted here, in full,
# together with the O-30 two-names-one-value purge body and the dual-token OCC
# conflict rule that the UI (single-token) can never exercise.
af_flow_e_trash_lifecycle() {
  banner "(e) TRASH: SOFT-DELETE -> RESTORE -> PURGE"
  local tokA="$AF_ADMIN_TOK"

  step "[e1] create two disposable work objects (real strategy roots)"
  # display_name is required (measured: 422 "A strategy display name is
  # required."), and it doubles as the Trash confirmation phrase in [e5].
  local root1 root2
  req POST /strategy-drafts -H "Authorization: Bearer $tokA" -H 'Content-Type: application/json' \
    -H "Idempotency-Key: $(af_key sd1)" -d '{"display_name":"RC harness trash subject A"}'
  root1="$(jfield "$LAST_BODY" strategy_root_id)"
  req POST /strategy-drafts -H "Authorization: Bearer $tokA" -H 'Content-Type: application/json' \
    -H "Idempotency-Key: $(af_key sd2)" -d '{"display_name":"RC harness OCC subject B"}'
  root2="$(jfield "$LAST_BODY" strategy_root_id)"
  { [ -n "$root1" ] && [ -n "$root2" ]; } \
    && ok "[e1] two work-object roots created ($root1, $root2)" \
    || { bad "[e1] strategy-draft create -> $LAST_STATUS $(af_peek "$LAST_BODY")"; return; }

  step "[e2] the dual OCC tokens are ONE value — a disagreement is 409, never a silent pick (O-12)"
  req DELETE "/entities/$root2" -H "Authorization: Bearer $tokA" \
    -H 'Content-Type: application/json' -H 'If-Match: rv-9' -H "Idempotency-Key: $(af_key occ)" \
    -d '{"expected_row_version":1}'
  { [ "$LAST_STATUS" = 409 ] && has "$LAST_BODY" 'OCC_TOKEN_CONFLICT'; } \
    && ok "[e2] body expected_row_version=1 vs If-Match rv-9 -> 409 OCC_TOKEN_CONFLICT" \
    || bad "[e2] contradictory dual tokens -> $LAST_STATUS $(af_peek "$LAST_BODY") (want 409 OCC_TOKEN_CONFLICT)"

  step "[e3] soft-delete moves the root into Trash (an entry MUST be written)"
  req DELETE "/entities/$root1" -H "Authorization: Bearer $tokA" \
    -H 'Content-Type: application/json' -H "Idempotency-Key: $(af_key del1)" \
    -d '{"reason":"RC acceptance harness"}'
  [ "$LAST_STATUS" = 204 ] \
    && ok "[e3] DELETE /entities/$root1 -> 204" \
    || bad "[e3] soft-delete -> $LAST_STATUS $(af_peek "$LAST_BODY")"
  req GET "/trash-entries?q=$root1" -H "Authorization: Bearer $tokA"
  local entry; entry="$(jfield "$LAST_BODY" trash_entry_id)"
  [ -z "$entry" ] && entry="$(jfield "$LAST_BODY" entry_id)"
  { [ "$LAST_STATUS" = 200 ] && [ -n "$entry" ]; } \
    && ok "[e3] the deleted root reached Admin Trash as entry $entry (K-06: no object vanishes silently)" \
    || { bad "[e3] no Trash entry for $root1 -> $LAST_STATUS $(af_peek "$LAST_BODY")"; return; }

  step "[e4] RESTORE — the leg the browser suite never exercises"
  req GET "/trash-entries/$entry/restore-preflight" -H "Authorization: Bearer $tokA"
  [ "$LAST_STATUS" = 200 ] \
    && ok "[e4] restore-preflight -> 200 (eligibility decided server-side before anything moves)" \
    || bad "[e4] restore-preflight -> $LAST_STATUS $(af_peek "$LAST_BODY")"
  req POST "/trash-entries/$entry/restore" -H "Authorization: Bearer $tokA" \
    -H 'Content-Type: application/json' -H "Idempotency-Key: $(af_key res)" -d '{}'
  { [ "$LAST_STATUS" = 200 ] || [ "$LAST_STATUS" = 202 ]; } \
    && ok "[e4] restore -> $LAST_STATUS (state=$(jfield "$LAST_BODY" deletion_state) status=$(jfield "$LAST_BODY" status))" \
    || bad "[e4] restore -> $LAST_STATUS $(af_peek "$LAST_BODY")"
  req GET "/trash-entries/$entry" -H "Authorization: Bearer $tokA"
  has "$LAST_BODY" 'restored' \
    && ok "[e4] the entry now reads RESTORED — Trash is recoverable, not a shredder" \
    || bad "[e4] entry did not report a restored status -> $(af_peek "$LAST_BODY")"

  step "[e5] PURGE — real re-auth, and the O-30 body carries BOTH state names"
  req DELETE "/entities/$root1" -H "Authorization: Bearer $tokA" \
    -H 'Content-Type: application/json' -H "Idempotency-Key: $(af_key del2)" \
    -d '{"reason":"RC acceptance harness — purge leg"}'
  req GET "/trash-entries?q=$root1" -H "Authorization: Bearer $tokA"
  entry="$(jfield "$LAST_BODY" trash_entry_id)"; [ -z "$entry" ] && entry="$(jfield "$LAST_BODY" entry_id)"
  local display; display="$(jfield "$LAST_BODY" display_name)"; [ -z "$display" ] && display="$root1"

  # F-21: an arbitrary string is not a proof. The proof is minted by the server
  # against the Admin's REAL password and is purpose-scoped to trash_purge.
  req POST "/trash-entries/$entry/purge" -H "Authorization: Bearer $tokA" \
    -H 'Content-Type: application/json' \
    -d "{\"confirmation_phrase\":\"$display\",\"reauth_proof\":\"not-a-real-proof\"}"
  { [ "$LAST_STATUS" != 202 ]; } \
    && ok "[e5] a fabricated reauth_proof is refused -> $LAST_STATUS (purge is genuinely re-auth gated)" \
    || bad "[e5] purge accepted a fabricated proof -> 202"

  req POST /auth/reauth -H "Authorization: Bearer $tokA" -H 'Content-Type: application/json' \
    -d "{\"password\":\"$AF_ADMIN_PW\",\"purpose\":\"trash_purge\"}"
  local proof; proof="$(jfield "$LAST_BODY" reauth_proof)"
  [ -n "$proof" ] && ok "[e5] POST /auth/reauth minted a purpose-scoped proof (value withheld)" \
    || { bad "[e5] reauth -> $LAST_STATUS $(af_peek "$LAST_BODY")"; return; }

  req POST "/trash-entries/$entry/purge" -H "Authorization: Bearer $tokA" \
    -H 'Content-Type: application/json' -H "Idempotency-Key: $(af_key purge)" \
    -d "{\"confirmation_phrase\":\"$display\",\"reauth_proof\":\"$proof\"}"
  if [ "$LAST_STATUS" = 202 ]; then
    ok "[e5] purge -> 202 (job=$(jfield "$LAST_BODY" purge_job_id)) — an ADMISSION, the erase runs on a worker"
    # O-30: doc 20 §7 names one field, §9.2 the other; both ship, same value.
    local ds rls; ds="$(jfield "$LAST_BODY" deletion_state)"; rls="$(jfield "$LAST_BODY" root_lifecycle_state)"
    { [ "$ds" = "purge_pending" ] && [ "$rls" = "purge_pending" ]; } \
      && ok "[e5] O-30 holds: deletion_state=$ds AND root_lifecycle_state=$rls (two names, one value)" \
      || bad "[e5] O-30 violated: deletion_state='$ds' root_lifecycle_state='$rls'"
  else
    bad "[e5] purge -> $LAST_STATUS $(af_peek "$LAST_BODY")"
  fi

  step "[e6] NON-NEGOTIABLE 3 — every Trash surface is Admin-gated ON THE SERVER"
  local path
  for path in "/trash-entries" "/trash-entries/$entry" "/trash-entries/$entry/restore-preflight"; do
    req GET "$path" -H "Authorization: Bearer $AF_USER_TOK"
    { [ "$LAST_STATUS" = 403 ] || [ "$LAST_STATUS" = 404 ]; } \
      && ok "[e6] USER -> GET $path = $LAST_STATUS" \
      || bad "[e6] USER read $path -> $LAST_STATUS"
  done
  req POST "/trash-entries/$entry/restore" -H "Authorization: Bearer $AF_USER_TOK" \
    -H 'Content-Type: application/json' -d '{}'
  { [ "$LAST_STATUS" = 403 ] || [ "$LAST_STATUS" = 404 ]; } \
    && ok "[e6] USER -> POST restore = $LAST_STATUS" || bad "[e6] USER reached restore -> $LAST_STATUS"
  req POST "/trash-entries/$entry/purge" -H "Authorization: Bearer $AF_USER_TOK" \
    -H 'Content-Type: application/json' -d '{"confirmation_phrase":"x","reauth_proof":"x"}'
  { [ "$LAST_STATUS" = 403 ] || [ "$LAST_STATUS" = 404 ]; } \
    && ok "[e6] USER -> POST purge = $LAST_STATUS" || bad "[e6] USER reached purge -> $LAST_STATUS"
}

# =============================================================================
# Browser layer — RUN the journeys that already exist (reuse, not reimplement)
# =============================================================================
# frontend/e2e is a self-contained Playwright project; .github/workflows/e2e.yml
# drives it with exactly these two commands against exactly this kind of stack.
# Called here with E2E_BASE_URL pointed at the isolated web port so the browser
# journeys and the server assertions above observe ONE database.
#
# If the toolchain is absent this records SKIP with the CI pointer. It never
# records PASS for a spec it did not run.
af_browser_layer() {
  banner "BROWSER LAYER — existing journeys, run against this stack"
  local web="http://localhost:${WEB_HOST_PORT}"
  local dir="$REPO_ROOT/frontend/e2e"
  local specs="specs/05-mainboard-ready-check-run.spec.ts specs/18-result-artifacts-drilldown.spec.ts specs/20-library-request-validation.spec.ts specs/06-trash-reauth.spec.ts"

  if ! command -v npm >/dev/null 2>&1; then
    af_skip "browser layer — npm not on PATH; flows (a)(b)(e) browser journeys NOT run here"
    info "      they are a CI gate: .github/workflows/e2e.yml -> 'Run the E2E suite'"
    return
  fi

  step "[browser] install the Playwright project (once per machine)"
  # `npm ci`, not `npm install`: this harness must not rewrite the committed
  # lockfile as a side effect of measuring something.
  ( cd "$dir" && npm ci --no-audit --no-fund >/dev/null 2>&1 ) \
    && ok "[browser] npm ci ok (lockfile untouched)" || { bad "[browser] npm ci failed"; return; }
  ( cd "$dir" && npx playwright install chromium >/dev/null 2>&1 ) \
    && ok "[browser] chromium available" || { af_skip "[browser] chromium download failed — specs not run"; return; }

  step "[browser] drive specs 05 + 18 (flow a), 20-library (flow b), 06 (flow e delete->purge)"
  # Reporter and output dir are forced OUT of the repo: playwright-report/ and
  # test-results/ are not in .gitignore, so the defaults would leave the working
  # tree dirty after a measurement run.
  local logf="${TMPDIR:-/tmp}/af-browser-$$.log"
  local outd="${TMPDIR:-/tmp}/af-playwright-$$"
  # E2E_API_BASE_URL is as load-bearing as E2E_BASE_URL: specs that assert SERVER
  # truth (utils/api.ts, spec 18) talk to the API directly and default to :8000,
  # the CI port. Without it they hit ECONNREFUSED against a stack on :18030 —
  # measured, not hypothetical.
  if ( cd "$dir" && E2E_BASE_URL="$web" E2E_API_BASE_URL="$BASE" \
        E2E_ADMIN_USERNAME="$AF_ADMIN_USER" E2E_ADMIN_PASSWORD="$AF_ADMIN_PW" E2E_ADMIN_EMAIL="$BOOTSTRAP_EMAIL" \
        npx playwright test $specs --reporter=list --output="$outd" ) >"$logf" 2>&1; then
    ok "[browser] all four journeys passed against this stack — $(grep -oE '[0-9]+ passed' "$logf" | tail -n1)"
  else
    bad "[browser] journeys FAILED — tail:"; tail -n 25 "$logf" | sed 's/^/      /'
  fi
}

# =============================================================================
af_run_all_flows() {
  af_bootstrap_actors || return
  af_flow_a_strategy_run
  af_flow_b_library_validation
  af_flow_c_esp_lifecycle_export
  af_flow_d_agent_signal_tools
  af_flow_e_trash_lifecycle
  af_browser_layer
}
