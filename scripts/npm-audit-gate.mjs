#!/usr/bin/env node
// Dependency-audit gate for the npm workspaces (frontend/ and frontend/e2e/).
//
// `npm audit --audit-level=high` on its own cannot be a CI gate here: a frontend
// advisory whose only published fix is a MAJOR upgrade would make the step red on
// every PR, and silencing that with `continue-on-error` would leave a step that can
// never fail — not a gate at all.
//
// So anything at or above the threshold severity that is NOT recorded as an
// exception fails the build. What changed in ADIM 44 is WHERE an exception may be
// recorded. This file used to carry its own FROZEN_ADVISORIES literal, which
// required neither an owner nor an expiry — an npm freeze was therefore a waiver
// nobody was accountable for and no calendar could ever expire, which the RC
// readiness report recorded as blocker P9-B2. That literal is gone. The one home
// for an exception is now .github/security-allowlist.json, which REQUIRES `owner`
// and `expires` and fails the build once the date passes. There is no second place
// left to write an unsigned freeze.
//
// Three freezes have lived here and all three were eventually DROPPED because the
// stated reason stopped being true — the brace-expansion pair (2026-08-03), js-yaml
// (2026-08-07, where the patch had shipped seven days BEFORE the freeze merged), and
// react-router GHSA-qwww-vcr4-c8h2 (2026-08-12). That is the pattern the `expires`
// field exists for: a freeze whose reason has expired is worse than no freeze,
// because it silently grants an exception nobody re-examined.
//
// react-router GHSA-qwww-vcr4-c8h2 was dropped, NOT carried over to the allowlist.
// Its reason said "every 7.x is affected and the only patched line is 8.3.0+, i.e.
// the v8 migration". The advisory was RE-SCOPED upstream on 2026-08-07T18:16:54Z —
// twenty minutes after PR #637 merged the corrected facts — into `>=7.12.0 <7.18.2`
// (first_patched 7.18.2) plus `>=8.0.0 <8.3.0`. The installed tree is react-router
// 7.18.2 exactly, the patched 7.x release, so npm audit reports it no more. An
// allowlist entry for it would have been an exception with no finding behind it.
//
// Usage: node scripts/npm-audit-gate.mjs <package-dir> [...more dirs]

import { execFileSync } from "node:child_process";
import * as path from "node:path";

import { assertScopeDeclared, enforceExpiry, loadAllowlist } from "./lib/security-allowlist.mjs";

const BLOCKING_SEVERITIES = ["high", "critical"];

// A package dir maps to exactly one allowlist scope. Requiring the scope to be
// DECLARED is what keeps "nothing is waived here" distinguishable from "this
// surface was never declared" — the two read identically otherwise.
const scopeFor = (relDir) => `npm:${relDir}`;

function runAudit(dir) {
  try {
    // npm exits 1 when advisories exist, so success and failure both carry the
    // JSON payload we need; only a missing/broken payload is a real error.
    return execFileSync("npm", ["audit", "--json"], {
      cwd: dir,
      encoding: "utf8",
      maxBuffer: 32 * 1024 * 1024,
    });
  } catch (err) {
    if (err.stdout) return err.stdout;
    throw err;
  }
}

function collectFindings(report) {
  const findings = new Map();
  for (const [pkg, entry] of Object.entries(report.vulnerabilities ?? {})) {
    if (!BLOCKING_SEVERITIES.includes(entry.severity)) continue;
    for (const via of entry.via ?? []) {
      if (typeof via !== "object") continue;
      const id = String(via.url ?? "").split("/").pop();
      if (!id) continue;
      findings.set(id, { id, pkg, severity: entry.severity, title: via.title ?? "" });
    }
  }
  return [...findings.values()];
}

function gateDir(relDir, scopes, entries) {
  const scope = scopeFor(relDir);
  assertScopeDeclared(scopes, scope);
  const frozen = entries.filter((e) => e.scope === scope);
  // Keyed by id AND package: an entry must not drift onto a different package that
  // happens to carry the same advisory id through a different dependency path.
  const allowed = new Set(frozen.map((f) => `${f.id}|${f.package}`));

  const report = JSON.parse(runAudit(path.resolve(relDir)));
  const findings = collectFindings(report);
  const counts = report.metadata?.vulnerabilities ?? {};
  console.log(
    `\n${relDir}: high=${counts.high ?? 0} critical=${counts.critical ?? 0} ` +
      `(moderate=${counts.moderate ?? 0} low=${counts.low ?? 0})`,
  );

  const key = (f) => `${f.id}|${f.pkg}`;
  const unrecorded = findings.filter((f) => !allowed.has(key(f)));
  for (const f of findings) {
    const mark = allowed.has(key(f)) ? "allowed " : "UNKNOWN ";
    const hit = frozen.find((e) => e.id === f.id && e.package === f.pkg);
    const tail = hit ? ` [expires ${hit.expires}, owner ${hit.owner}]` : "";
    console.log(`  ${mark} ${f.id} ${f.severity} ${f.pkg} — ${f.title.slice(0, 90)}${tail}`);
  }
  // Same reasoning as security-allowlist-gate.mjs: an exception whose finding has
  // stopped existing is an exception nobody re-examined, so surface it — but do not
  // fail on a vulnerability that went away.
  for (const e of frozen) {
    if (!findings.some((f) => key(f) === `${e.id}|${e.package}`)) {
      console.log(`  note     ${e.id} (${e.package}) is allowlisted but no longer reported — delete the entry.`);
    }
  }
  return unrecorded;
}

const dirs = process.argv.slice(2);
if (dirs.length === 0) {
  console.error("usage: node scripts/npm-audit-gate.mjs <package-dir> [...]");
  process.exit(2);
}

// The WHOLE allowlist expires here, not just the npm scopes: this gate runs in
// ci.yml on every push and PR, while the container gate lives in security.yml. If
// each gate only expired its own scopes, an exception's calendar would depend on
// which workflow happened to run.
const { scopes, entries } = loadAllowlist();
enforceExpiry(entries);

const unrecorded = dirs.flatMap((dir) => gateDir(dir, scopes, entries).map((f) => ({ dir, ...f })));
if (unrecorded.length > 0) {
  console.error(
    `\nFAIL — ${unrecorded.length} unrecorded high/critical advisory(ies). Fix them, or ` +
      `add a reviewed entry to .github/security-allowlist.json with a scope of ` +
      `npm:<dir>, an owner, a justification and an expiry:`,
  );
  for (const f of unrecorded) console.error(`  ${f.dir}: ${f.id} ${f.severity} ${f.pkg}`);
  process.exit(1);
}
console.log("\nOK — no unrecorded high/critical advisories.");
