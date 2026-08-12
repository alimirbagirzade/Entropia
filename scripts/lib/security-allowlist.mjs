#!/usr/bin/env node
// Shared reader for .github/security-allowlist.json.
//
// WHY THIS MODULE EXISTS (ADIM 44)
//   This repo used to freeze security findings in two unrelated idioms. The
//   container scan read .github/security-allowlist.json, which REQUIRES an
//   `owner` and an `expires` and fails the build once the date passes. The npm
//   audit gate carried its own hardcoded FROZEN_ADVISORIES literal, which
//   required neither — so an npm freeze was a waiver nobody was accountable for
//   and no calendar could ever expire. The RC readiness report recorded that
//   asymmetry as blocker P9-B2 (§6.4), quoting this repo's own gate header back
//   at itself: "their freezes expire only when a human happens to notice. Here
//   the calendar notices."
//
//   The asymmetry is closed by deletion, not by documentation: FROZEN_ADVISORIES
//   is gone and npm-audit-gate.mjs now reads the same signed allowlist the
//   container gate reads. A future npm freeze therefore CANNOT be unsigned —
//   there is no longer a second place to put one.
//
// Both gates call loadAllowlist() then enforceExpiry() before looking at any
// scan output, so an expired exception fails the build whether or not the
// finding behind it still exists.

import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";

export const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
export const ALLOWLIST_PATH = path.join(REPO_ROOT, ".github", "security-allowlist.json");
export const REQUIRED_FIELDS = ["id", "scope", "package", "owner", "justification", "expires"];
export const MAX_EXCEPTION_DAYS = 90;

const DAY_MS = 24 * 60 * 60 * 1000;

export function die(lines) {
  for (const line of lines) console.error(line);
  process.exit(1);
}

// Returns { scopes: Set<string>, entries: Array }. A malformed allowlist is a
// failure, not a reason to skip the gate: an entry missing `expires` would
// otherwise be an exception that never expires.
export function loadAllowlist() {
  const raw = JSON.parse(fs.readFileSync(ALLOWLIST_PATH, "utf8"));
  const scopes = new Set(raw.scopes ?? []);
  const entries = raw.entries ?? [];
  const problems = [];

  entries.forEach((entry, i) => {
    for (const field of REQUIRED_FIELDS) {
      const value = entry[field];
      if (typeof value !== "string" || value.trim() === "") {
        problems.push(`entries[${i}]: missing or empty required field "${field}"`);
      }
    }
    if (entry.scope && !scopes.has(entry.scope)) {
      problems.push(`entries[${i}]: scope "${entry.scope}" is not one of ${[...scopes].join(", ")}`);
    }
    if (entry.expires && !/^\d{4}-\d{2}-\d{2}$/.test(entry.expires)) {
      problems.push(`entries[${i}]: expires "${entry.expires}" is not YYYY-MM-DD`);
    }
  });

  if (problems.length) {
    die(["security-allowlist.json is malformed:", ...problems.map((p) => `  ${p}`)]);
  }
  return { scopes, entries };
}

// Fails on any entry past its expiry, warns on any window longer than the cap.
// Called by EVERY gate over the WHOLE list, not just the scopes that gate reads:
// otherwise an npm exception's calendar would depend on the container scan job
// having run, which is a different workflow with a different trigger set.
export function enforceExpiry(entries) {
  // Compare whole UTC days so the verdict does not depend on the runner's clock
  // time of day — a gate that flips mid-afternoon is a flaky gate.
  const today = new Date();
  const todayUtc = Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate());
  const expired = [];
  const overlong = [];

  for (const entry of entries) {
    const [y, m, d] = entry.expires.split("-").map(Number);
    const expiresUtc = Date.UTC(y, m - 1, d);
    if (expiresUtc < todayUtc) {
      expired.push(`  EXPIRED ${entry.expires}  ${entry.id} (${entry.package}, ${entry.scope}) — owner ${entry.owner}`);
    } else if (expiresUtc - todayUtc > MAX_EXCEPTION_DAYS * DAY_MS) {
      overlong.push(`  ${entry.id}: expires ${entry.expires}, more than ${MAX_EXCEPTION_DAYS} days out`);
    }
  }

  if (overlong.length) {
    console.error(`WARN — exception windows longer than ${MAX_EXCEPTION_DAYS} days:`);
    for (const line of overlong) console.error(line);
  }
  if (expired.length) {
    die([
      "FAIL — expired security exceptions. Re-examine each one: fix it, or renew the",
      "entry with a fresh justification and a new expiry. Do not bump the date alone.",
      ...expired,
    ]);
  }
}

// A scope a gate is about to read must be DECLARED, even when it holds no
// entries. Without this an unknown scope silently resolves to "nothing is
// allowlisted", which reads identically to "everything here is clean".
export function assertScopeDeclared(scopes, scope) {
  if (!scopes.has(scope)) {
    die([
      `scope "${scope}" is not declared in .github/security-allowlist.json.`,
      `Declared scopes: ${[...scopes].join(", ")}`,
      "Add it to `scopes` before gating a new surface.",
    ]);
  }
}
