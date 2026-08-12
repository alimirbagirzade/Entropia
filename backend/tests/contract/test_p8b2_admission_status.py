"""RC P8-B2 — the HTTP status of every DURABLE ADMISSION endpoint, adjudicated.

A durable admission is an endpoint that writes a QUEUED ``jobs`` row and returns BEFORE
the work exists; the worker lands the result later. Thirteen HTTP surfaces do this, and
they did not agree on a status: four Create-Package ones returned a bare ``200``, the
library validation-run ``201``, the other eight ``202``.

The split below is NOT a style preference, it is what canonical says endpoint by endpoint:

* ``pre-check`` — doc 07 §10.3: "202 accepted or idempotent completed response: job/scan
  id, state precheck_pending/checking". Shipped 200 -> ALIGNED to 202.
* ``generate-candidate`` — Master Technical Reference §7.1 spells the wire contract out
  literally ("POST /package-requests/{id}/generate-candidate -> 202 Accepted"), §4.2
  repeats it ("202 Accepted + job_id dondur"), doc 07 §10.3 repeats it again. Shipped
  200 -> ALIGNED to 202.
* ``validate`` / ``baseline-parse`` — canonical describes the ASYNC BEHAVIOUR (doc 06 §7,
  MTR §13) but names NO status, and for baseline-parse names no endpoint at all. ADIM 41
  left both at the shipped 200 and referred the gap to the product owner. **The PO decided
  on 2026-08-12: align both to 202.** Shipped 200 -> DECIDED 202. The distinction from the
  two above survives in ``_EXPECTED``: those are ALIGNED (canonical named the code), these
  are PO (canonical is silent and a human chose). Do not collapse the two labels — a future
  reader who reads "202 everywhere" as canonical would treat a decision as a citation.
* the remaining nine keep their shipped statuses; they are pinned here so a later
  "let's make these consistent" sweep cannot flip a published contract by accident.

The endpoint SET is derived, never hand-listed: ``_admission_commands`` walks the
application layer for everything that transitively reaches ``enqueue_job``, and
``_admission_routes`` maps those onto the route table. A new durable admission that
nobody classified therefore FAILS here instead of quietly inventing a fourteenth answer.
"""

from __future__ import annotations

import ast
import pathlib
from typing import Any

import pytest

_APPLICATION = pathlib.Path(__file__).resolve().parents[2] / "src/entropia/application"
_ROUTES = pathlib.Path(__file__).resolve().parents[2] / "src/entropia/apps/api/routes"

# path -> (status, why). ALIGNED = canonical named the code; PO = canonical is silent.
_EXPECTED: dict[str, tuple[int, str]] = {
    # Create Package plane
    "/create-package/requests/{request_id}/pre-check": (202, "ALIGNED doc 07 §10.3"),
    "/create-package/requests/{request_id}/generate-candidate": (202, "ALIGNED MTR §7.1"),
    "/create-package/requests/{request_id}/validate": (202, "PO 2026-08-12 — canonical silent"),
    "/create-package/requests/{request_id}/baseline-parse": (
        202,
        "PO 2026-08-12 — canonical silent",
    ),
    # Shipped elsewhere, unchanged by P8-B2
    "/library/{entity_id}/validation-runs": (201, "shipped; canonical silent on status"),
    "/mainboard-compositions/{composition_id}/backtest-runs": (202, "doc 15 §10 '201/202'"),
    "/backtest-runs/{run_id}/retries": (202, "shipped"),
    "/market-datasets/{entity_id}/analysis": (202, "shipped"),
    "/research-datasets/{entity_id}/analysis": (202, "shipped"),
    "/trade-logs/imports": (202, "shipped"),
    "/trading-signals/imports": (202, "shipped"),
    "/package-imports": (202, "shipped"),
    "/trash-entries/{trash_entry_id}/purge": (202, "doc 20 §7 '202 job reference'"),
}


def _called_names(node: ast.AST) -> set[str]:
    out: set[str] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            func = sub.func
            if isinstance(func, ast.Attribute):
                out.add(func.attr)
            elif isinstance(func, ast.Name):
                out.add(func.id)
    return out


def _admission_commands() -> set[str]:
    """Every application function that transitively enqueues a durable job."""
    calls: dict[str, set[str]] = {}
    for path in sorted(_APPLICATION.rglob("*.py")):
        for node in ast.parse(path.read_text()).body:
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                calls.setdefault(node.name, set()).update(_called_names(node))
    reached = {"enqueue_job"}
    changed = True
    while changed:
        changed = False
        for name, called in calls.items():
            if name not in reached and called & reached:
                reached.add(name)
                changed = True
    return reached - {"enqueue_job"}


def _admission_routes() -> dict[str, str]:
    """route path -> handler name, for every route whose handler calls an admission."""
    admissions = _admission_commands()
    found: dict[str, str] = {}
    for path in sorted(_ROUTES.rglob("*.py")):
        module = ast.parse(path.read_text())
        constants = {
            target.id: node.value.value
            for node in module.body
            if isinstance(node, ast.Assign)
            for target in node.targets
            if isinstance(target, ast.Name) and isinstance(node.value, ast.Constant)
        }
        for node in ast.walk(module):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            if not _called_names(node) & admissions:
                continue
            for dec in node.decorator_list:
                if not (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute)):
                    continue
                if dec.func.attr not in {"post", "put", "patch", "delete"} or not dec.args:
                    continue
                arg = dec.args[0]
                if isinstance(arg, ast.Constant):
                    found[str(arg.value)] = node.name
                elif isinstance(arg, ast.Name) and arg.id in constants:
                    found[str(constants[arg.id])] = node.name
    return found


def _status_of(app: Any, path: str) -> int:
    """The status the LIVE app publishes for this path's mutating operation."""
    schema = app.openapi()["paths"][f"/api/v1{path}"]
    codes = {
        code
        for method, op in schema.items()
        if method in {"post", "put", "patch", "delete"}
        for code in op.get("responses", {})
        if code.startswith("2")
    }
    assert len(codes) == 1, f"{path}: expected one success code, got {sorted(codes)}"
    return int(codes.pop())


@pytest.mark.contract
def test_every_durable_admission_endpoint_is_classified() -> None:
    """A NEW admission route must be adjudicated here — it cannot arrive unclassified."""
    discovered = set(_admission_routes())
    assert discovered == set(_EXPECTED), (
        "durable-admission route set drifted from the P8-B2 adjudication; "
        f"new/unclassified: {sorted(discovered - set(_EXPECTED))}; "
        f"stale entries: {sorted(set(_EXPECTED) - discovered)}"
    )


@pytest.mark.contract
def test_the_two_endpoints_canonical_gives_a_status_are_202(app) -> None:
    """doc 07 §10.3 and MTR §7.1 name 202 for these two; the wire now agrees."""
    assert _status_of(app, "/create-package/requests/{request_id}/pre-check") == 202
    assert _status_of(app, "/create-package/requests/{request_id}/generate-candidate") == 202


@pytest.mark.contract
def test_validate_and_baseline_parse_are_202_by_product_owner_decision(app) -> None:
    """A DECISION, not a citation — the distinction is the point of this test.

    Both endpoints are durable admissions with no canonical status to align to. ADIM 41
    left them at the shipped 200 rather than invent a wire contract in a canonical gap,
    and referred the gap to the product owner. The PO chose 202 on 2026-08-12: a 200
    advertises a completed result these responses do not carry, and the four
    Create-Package admissions now answer with one status.

    Nothing about the endpoints' semantics moved — both enqueued a durable job before
    this slice and both still do. If a later reader looks for the canonical page that
    mandates 202 here, there is none, and finding none must not be read as licence to
    revert: the authority is the recorded decision, kept alongside its reasoning on
    ``ValidationRunAcceptedResponse`` / ``BaselineParseAcceptedResponse``.
    """
    assert _status_of(app, "/create-package/requests/{request_id}/validate") == 202
    assert _status_of(app, "/create-package/requests/{request_id}/baseline-parse") == 202


@pytest.mark.contract
def test_the_other_nine_admissions_keep_their_published_status(app) -> None:
    """A consistency sweep must not silently re-cut a shipped contract."""
    for path, (status, why) in _EXPECTED.items():
        if path.startswith("/create-package/"):
            continue
        assert _status_of(app, path) == status, f"{path} ({why})"


@pytest.mark.contract
def test_every_202_admission_body_is_published_in_the_schema(app) -> None:
    """202 with a bare ``dict`` would hide the body from the schema exactly as the purge
    202 once did (O-30). All four Create-Package admission bodies are typed and their keys
    are visible — the two the PO moved on 2026-08-12 included, which is why flipping the
    status alone would not have been the whole change."""
    schema = app.openapi()
    components = schema["components"]["schemas"]
    for name, keys in (
        (
            "PrecheckAcceptedResponse",
            {
                "request_id",
                "job_id",
                "status",
                "state",
                "scan_id",
                "attempt_no",
                "resolved",
                "missing",
                "warnings",
                "registry_fingerprint",
                "request_version",
            },
        ),
        (
            "CandidateAcceptedResponse",
            {"request_id", "state", "candidate_hash", "job_id", "request_version"},
        ),
        (
            "ValidationRunAcceptedResponse",
            {
                "request_id",
                "validation_run_id",
                "attempt_no",
                "status",
                "state",
                "checks",
                "job_id",
                "request_version",
            },
        ),
        (
            "BaselineParseAcceptedResponse",
            {
                "request_id",
                "baseline_asset_id",
                "attempt_no",
                "parse_status",
                "parser_version",
                "parse_report",
                "job_id",
                "request_version",
            },
        ),
    ):
        assert name in components, f"{name} is not published in the OpenAPI schema"
        assert set(components[name]["properties"]) == keys
