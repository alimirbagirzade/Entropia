"""Shared pytest fixtures.

Unit/contract tests run without external infra by exercising the ASGI app via
httpx. Tests marked `integration` require the Docker stack (postgres/redis/minio).
"""

from __future__ import annotations

import os

import pytest

# Deterministic, infra-free defaults for the test process.
os.environ.setdefault("ENTROPIA_ENV", "local")
os.environ.setdefault("ENTROPIA_LOG_FORMAT", "console")


@pytest.fixture(scope="session")
def app():
    from entropia.apps.api.main import create_app

    return create_app()
