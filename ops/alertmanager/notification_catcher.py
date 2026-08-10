#!/usr/bin/env python3
"""A test receiver that stands at the END of the notification path (ADIM 31).

WHY THIS EXISTS. `scripts/alert-rules-gate.sh` proves the alert rules are
CORRECT: valid PromQL over metrics that exist, thresholds derived from shipped
configuration, and — since ADIM 26 — evaluated to `alertstate="firing"` against
synthetic series. It never asks who receives them. That distinction is the whole
of docs/releases/Entropia_V18_RC_Readiness_2026-08-07.md §6.3, and it is why this
file is not a mock of anything: it is a real HTTP server that a real Alertmanager
POSTs to, so that "the notification arrived" is an observation rather than an
inference from configuration.

WHAT IT IS NOT. It is not a receiver anybody deploys. It has no auth, no storage
and no delivery guarantee; it prints what it was given and returns 200. It exists
only for scripts/alert-notification-proof.sh, which points
ALERTMANAGER_NOTIFY_URL at it and then asserts that a specific alert reached it.
Nothing in docker-compose.yml references it — it lives in the proof overlay,
ops/alertmanager/docker-compose.proof.yml, so it cannot be started by accident.

Standard library only, deliberately: this runs in a stock python image with no
build step, so the proof harness cannot itself become something that needs
maintaining.
"""

from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

#: Grepped verbatim by scripts/alert-notification-proof.sh. Changing it breaks
#: the proof loudly, which is the intent — a silent rename would make the proof
#: report "nothing arrived" for a path that works.
MARKER = "NOTIFICATION_RECEIVED"

LISTEN_PORT = int(os.environ.get("CATCHER_PORT", "9099"))
MAX_BODY_BYTES = 1_048_576


def _emit(payload: dict) -> None:
    """One line, flushed. `docker compose logs` is the transport."""
    print(f"{MARKER} {json.dumps(payload, sort_keys=True)}", flush=True)


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802 — BaseHTTPRequestHandler's contract
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY_BYTES:
            self.send_error(413, "payload too large")
            return
        raw = self.rfile.read(length)

        try:
            body = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            # Report it rather than crash: a malformed body is itself a finding
            # about the path, and swallowing it would make the proof green for
            # the wrong reason.
            _emit({"path": self.path, "error": "body is not JSON", "bytes": len(raw)})
            self.send_response(200)
            self.end_headers()
            return

        # Flatten to exactly what the proof asserts on. The full Alertmanager
        # webhook envelope is large and mostly stable boilerplate; the fields
        # below are the ones that answer "did THIS alert, at THIS severity,
        # through THIS receiver, actually arrive".
        _emit(
            {
                "path": self.path,
                "receiver": body.get("receiver"),
                "status": body.get("status"),
                "groupLabels": body.get("groupLabels"),
                "commonLabels": body.get("commonLabels"),
                "alerts": [
                    {
                        "status": alert.get("status"),
                        "labels": alert.get("labels"),
                        "annotations": {
                            # Only the two annotations the proof reads. Alert
                            # annotations in this repo are paragraphs; echoing
                            # all nine would bury the assertion in the log.
                            "summary": (alert.get("annotations") or {}).get("summary"),
                            "runbook": (alert.get("annotations") or {}).get("runbook"),
                        },
                    }
                    for alert in (body.get("alerts") or [])
                ],
            }
        )

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def do_GET(self) -> None:  # noqa: N802
        """Readiness for the proof script's wait loop; never receives alerts."""
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"catcher-ready")

    def log_message(self, fmt: str, *args: object) -> None:
        """Access logging goes to stderr so it cannot be mistaken for a MARKER line."""
        sys.stderr.write(f"catcher: {fmt % args}\n")


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", LISTEN_PORT), _Handler)
    print(f"catcher: listening on :{LISTEN_PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
