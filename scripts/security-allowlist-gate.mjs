#!/usr/bin/env node
// Release-blocking gate for container vulnerability scans.
//
// Trivy is run with --ignore-unfixed, so the findings it reports are the ones we
// could actually act on today. This gate turns that report into a verdict:
//
//   * ANY CRITICAL/HIGH finding with a published fix, not on the allowlist -> FAIL.
//   * ANY allowlist entry past its `expires` date -> FAIL, even if the finding is
//     long gone. An exception nobody re-examines is not an exception, it is a hole.
//     npm-audit-gate.mjs used to lack exactly this — its FROZEN_ADVISORIES literal
//     required no owner and no expiry — which the RC readiness report recorded as
//     blocker P9-B2. ADIM 44 deleted that literal and pointed the npm gate at this
//     same allowlist, so both gates now share scripts/lib/security-allowlist.mjs and
//     both let the calendar notice. (The a11y scan's ACCEPTED_SERIOUS_RULES stays
//     separate on purpose: it freezes rule ids, not findings.)
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

import { assertScopeDeclared, die, enforceExpiry, loadAllowlist } from "./lib/security-allowlist.mjs";

const BLOCKING_SEVERITIES = new Set(["CRITICAL", "HIGH"]);

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

  // The whole list expires here, not just the container scopes: an npm exception's
  // calendar must not depend on which workflow happened to run.
  const { scopes, entries } = loadAllowlist();
  enforceExpiry(entries);

  const findings = [];
  const scanned = new Set();
  for (const arg of args) {
    const sep = arg.indexOf("=");
    if (sep < 0) die([`bad argument "${arg}" — expected <scope>=<path>`]);
    const scope = arg.slice(0, sep);
    assertScopeDeclared(scopes, scope);
    scanned.add(scope);
    findings.push(...collectFindings(scope, arg.slice(sep + 1)));
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

  // Only entries whose scope this run actually scanned. An npm:* entry is not
  // "unreported" here — it was never looked for; npm-audit-gate.mjs owns that scope
  // and prints the same note for it. Warning on scopes we did not read would train
  // the reader to ignore the line.
  for (const e of entries) {
    if (scanned.has(e.scope) && !matched.has(`${e.scope}|${e.id}|${e.package}`)) {
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
