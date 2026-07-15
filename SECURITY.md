# Security Policy

## Reporting a vulnerability

Entropia is proprietary software (see [`LICENSE`](LICENSE)) handling
financial strategy and market data. If you discover a security
vulnerability, please report it privately — **do not open a public GitHub
issue.**

**How to report:**

1. Use GitHub's private vulnerability reporting: go to the
   [Security tab](../../security/advisories/new) of this repository and
   click **Report a vulnerability**, or
2. Email the repository owner directly with:
   - A description of the vulnerability and its potential impact.
   - Steps to reproduce (proof-of-concept code or requests welcome).
   - The affected component (backend route/command, frontend page, worker
     job, infrastructure config) and, if known, the affected commit/tag.

Please do not test against any deployed/hosted instance beyond what is
necessary to demonstrate the issue, and do not access, modify, or exfiltrate
data belonging to others.

## Response process

- We aim to acknowledge reports within **5 business days**.
- Confirmed vulnerabilities are triaged by severity — critical patches
  within 24 hours, high within 7 days — and a fix is developed on a private
  branch.
- We will credit reporters in the fix's changelog/commit unless anonymity is
  requested.

## Scope

In scope:

- The FastAPI backend (`backend/`) — auth, session handling, OCC/idempotency
  enforcement, SQL/data access, worker job dispatch.
- The React frontend (`frontend/`) — XSS, CSRF, auth/session handling,
  sensitive data exposure in the client.
- Infrastructure config in this repository (Docker Compose, CI workflows).

Out of scope:

- Findings that require physical access to a maintainer's machine.
- Vulnerabilities in third-party dependencies without a demonstrated,
  Entropia-specific exploit path (report those upstream instead — we track
  and patch known CVEs on our own update cadence).
- Denial-of-service reports based purely on volume/traffic.

## Supported versions

This project does not yet publish tagged releases; security fixes are
applied to `main` only. Once versioned releases begin, this section will be
updated with a support matrix.
