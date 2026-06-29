"""Run a Dramatiq worker bound to one or more canonical queues.

python -m entropia.apps.worker --queues default,maintenance
"""

from __future__ import annotations

import argparse

from dramatiq.cli import main as dramatiq_main
from dramatiq.cli import make_argument_parser

from entropia.config import get_settings
from entropia.infrastructure.observability import configure_logging, get_logger


def run() -> None:
    configure_logging()
    settings = get_settings()

    parser = argparse.ArgumentParser(description="Entropia worker plane")
    parser.add_argument(
        "--queues",
        default="default",
        help="Comma-separated canonical queues this worker consumes.",
    )
    parser.add_argument("--processes", type=int, default=1)
    parser.add_argument("--threads", type=int, default=settings.worker_concurrency)
    known, _ = parser.parse_known_args()

    get_logger("worker").info("worker.boot", queues=known.queues)

    argv = [
        "entropia.apps.worker",  # broker + actor discovery module
        "--queues",
        *known.queues.split(","),
        "--processes",
        str(known.processes),
        "--threads",
        str(known.threads),
    ]
    dramatiq_args = make_argument_parser().parse_args(argv)  # type: ignore[no-untyped-call]
    dramatiq_main(dramatiq_args)  # type: ignore[no-untyped-call]


if __name__ == "__main__":
    run()
