#!/usr/bin/env node
// Release-blocking gate for container vulnerability scans.
//
// Trivy is run with --ignore-unfixed, so the findings it reports are the ones we
// could actually act on today. This gate turns that report into a verdict:
//
//   * ANY CRITICAL/HIGH finding with a published fix, not on the allowlist -> FAIL.
//   * ANY allowlist entry past its `expires` date -> FAIL, even if the finding is
//     long gone. An exception nobody re-examines is not an exception, it is a hole.
//     This is the part the two older gates in this repo (npm-audit-gate.mjs's
//     FROZEN_ADVISORIES, the a11y scan's ACCEPTED_SERIOUS_RULES) do not have: their
//     freezes expire only when a human happens to notice. Here the calendar notices.
//   * An allowlist entry that no longer matches any finding -> WARN. Same reasoning
//     as npm-audit-gate.mjs: a freeze whose reason has expired grants an exception
//     nobody re-examined, so surface it — but do not fail on a vulnerability that
//     stopped existing.
//
// The gate re-derives "has a published fix" from FixedVersion itself rather than
// trusting the --ignore-unfixed flag, so dropping the flag cannot silently widen it.
//
// Usage: node scripts/security-allowlist-gate.mjs <scope>=<trivy-report.json> [...]
//   e.g. node scripts/security-allowlist-gate.mjs \
//          container:backend=be.json container:frontend=fe.json

import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const ALLOWLIST_PATH = path.join(REPO_ROOT, ".github", "security-allowlist.json");
const BLOCKING_SEVERITIES = new Set(["CRITICAL", "HIGH"]);
const REQUIRED_FIELDS = ["id", "scope", "package", "owner", "justification", "expires"];
const MAX_EXCEPTION_DAYS = 90;
const DAY_MS = 24 * 60 * 60 * 1000;

function die(lines) {
  for (const line of lines) console.error(line);
  process.exit(1);
}

function loadAllowlist() {
  const raw = JSON.parse(fs.readFileSync(ALLOWLIST_PATH, "utf8"));
  const scopes = new Set(raw.scopes ?? []);
  const problems = [];
  const entries = raw.entries ?? [];

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

  // A malformed allowlist is a failure, not a reason to skip the gate: an entry
  // missing `expires` would otherwise be an exception that never expires.
  if (problems.length) {
    die(["security-allowlist.json is malformed:", ...problems.map((p) => `  ${p}`)]);
  }
  return entries;
}

function enforceExpiry(entries) {
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

function collectFindings(scope, reportPath) {
  const report = JSON.parse(fs.readFileSync(reportPath, "utf8"));
  const findings = [];
  for (const result of report.Results ?? []) {
    for (const vuln of result.Vulnerabilities ?? []) {
      if (!BLOCKING_SEVERITIES.has(vuln.Severity)) continue;
      // No published fix means there is nothing to do but wait for upstream, so it
      // is not a gate failure. Derived here, not inherited from the CLI flag.
      if (!vuln.FixedVersion) continue;
      findings.push({
        scope,
        id: vuln.VulnerabilityID,
        pkg: vuln.PkgName,
        severity: vuln.Severity,
        installed: vuln.InstalledVersion,
        fixed: vuln.FixedVersion,
        title: vuln.Title ?? "",
      });
    }
  }
  return findings;
}

function main() {
  const args = process.argv.slice(2);
  if (args.length === 0) {
    die(["usage: security-allowlist-gate.mjs <scope>=<trivy-report.json> [...]"]);
  }

  const entries = loadAllowlist();
  enforceExpiry(entries);

  const findings = [];
  for (const arg of args) {
    const sep = arg.indexOf("=");
    if (sep < 0) die([`bad argument "${arg}" — expected <scope>=<path>`]);
    findings.push(...collectFindings(arg.slice(0, sep), arg.slice(sep + 1)));
  }

  const matched = new Set();
  const blocking = [];
  for (const f of findings) {
    const hit = entries.find((e) => e.scope === f.scope && e.id === f.id && e.package === f.pkg);
    if (hit) {
      matched.add(`${hit.scope}|${hit.id}|${hit.package}`);
      console.log(`  allowed  ${f.severity} ${f.id} ${f.pkg} (${f.scope}) — expires ${hit.expires}, owner ${hit.owner}`);
    } else {
      blocking.push(f);
    }
  }

  for (const e of entries) {
    if (!matched.has(`${e.scope}|${e.id}|${e.package}`)) {
      console.error(`WARN — allowlisted but not reported: ${e.id} (${e.package}, ${e.scope}). If it is fixed, delete the entry.`);
    }
  }

  if (blocking.length) {
    die([
      `FAIL — ${blocking.length} fixable CRITICAL/HIGH finding(s) with no recorded exception:`,
      ...blocking.map(
        (f) => `  ${f.severity.padEnd(8)} ${f.id.padEnd(20)} ${f.pkg} ${f.installed} -> ${f.fixed}  [${f.scope}]  ${f.title}`,
      ),
      "",
      "Fix it (bump the base image / dependency), or add a reviewed entry to",
      ".github/security-allowlist.json with an owner, a justification and an expiry.",
    ]);
  }

  console.log(`OK — ${findings.length} fixable CRITICAL/HIGH finding(s), all accounted for.`);
}

main();
