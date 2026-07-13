"""GAP-07b — package baseline CSV upload/parse chain + mode-aware baseline gate.

Auto-skips when no PostgreSQL is reachable (tests/integration/conftest.py). Covers:
upload -> parse happy path; incomplete metadata -> BASELINE_METADATA_INVALID; an
unparseable CSV -> PARSE_FAILED; a non-CSV -> FILE_TYPE_NOT_ALLOWED; an equivalence-
claiming request cannot publish without a passed baseline (BASELINE_REQUIRED) but can
once it has one; a non-claiming request needs no baseline; re-upload is a new immutable
attempt; upload/validate write audit events.
"""

from __future__ import annotations

import hashlib
from typing import Any

import pytest
from sqlalchemy import func, select

from entropia.application.commands import create_package as cp_cmd
from entropia.domain.create_package.enums import (
    BaselineParseStatus,
    CreationMode,
    SourceLanguage,
)
from entropia.domain.esp.enums import ResolverTrustState, RuntimeAdapter
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import (
    ApprovalState,
    PackageKind,
    PrincipalType,
    Role,
    VisibilityScope,
)
from entropia.domain.package.enums import PackageValidationState
from entropia.infrastructure.postgres.models import BaselineAsset, Principal
from entropia.infrastructure.postgres.repositories import create_package as cp_repo
from entropia.infrastructure.postgres.repositories import esp as esp_repo
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.infrastructure.postgres.repositories import rationale as rationale_repo
from entropia.infrastructure.s3 import datasets
from entropia.shared.errors import (
    BaselineAssetNotFound,
    BaselineMetadataInvalid,
    BaselineParseFailed,
    BaselineRequired,
    FileTypeNotAllowedError,
)

pytestmark = pytest.mark.integration

ADMIN = Actor(principal_id="user_admin", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)
OWNER = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)

_RSI_SIG = {
    "params": [{"name": "source", "type": "series"}, {"name": "length", "type": "int"}],
    "return": "series",
}
_RSI_DEP = {"key": "ta.rsi", "signature": _RSI_SIG}
_INDICATOR_OUTPUT = {"kind": "directional_signal"}

_FULL_METADATA = {
    "provider": "tradingview",
    "symbol": "BTCUSDT",
    "timeframe": "1h",
    "range": {"start": "2024-01-01", "end": "2024-06-01"},
    "timezone": "UTC",
    "settings": {"rsi_length": 14},
    "source_revision_context": "pine v5 @ abcdef",
}
_GOOD_CSV = b"time,rsi\n2024-01-01T00:00:00Z,55.2\n2024-01-01T01:00:00Z,48.7\n"


@pytest.fixture
def fake_object_store(monkeypatch) -> dict[str, bytes]:
    """In-process object storage so upload + parse read run without MinIO."""
    store: dict[str, bytes] = {}

    def _put(request_entity_id: str, data: bytes, *, content_type: str | None = None):
        digest = hashlib.sha256(data).hexdigest()
        key = f"create-package/baseline/{request_entity_id}/{digest}"
        store[key] = data
        return key, digest

    def _get(object_key: str) -> bytes:
        return store[object_key]

    monkeypatch.setattr(datasets, "put_baseline_bytes", _put)
    monkeypatch.setattr(datasets, "get_raw_bytes", _get)
    return store


async def _count(session, model) -> int:
    return int((await session.execute(select(func.count()).select_from(model))).scalar_one())


async def _seed_principals(session) -> None:
    for pid in ("user_admin", "user_1"):
        if await session.get(Principal, pid) is None:
            session.add(Principal(principal_id=pid, principal_type=PrincipalType.HUMAN))
    await session.flush()


async def _seed_python_resolver(session, *, key: str = "ta.rsi") -> str:
    root, _detail, revision = await pkg_repo.create_package(
        session,
        owner_principal_id="user_admin",
        created_by_principal_id="user_admin",
        package_kind=PackageKind.EMBEDDED_SYSTEM,
        input_contract={"resolver_key": key},
        output_contract={"return": "series"},
        dependency_snapshot={},
        visibility_scope=VisibilityScope.SYSTEM,
        validation_state=PackageValidationState.PASSED,
        approval_state=ApprovalState.APPROVED,
    )
    esp_repo.add_resolver_contract(
        session,
        entity_id=root.entity_id,
        revision_id=revision.revision_id,
        canonical_key=key,
        signature=_RSI_SIG,
        runtime_adapter=RuntimeAdapter.PYTHON,
    )
    esp_repo.upsert_registry_entry(
        session,
        canonical_key=key,
        package_entity_id=root.entity_id,
        runtime_adapter=RuntimeAdapter.PYTHON,
        trust_state=ResolverTrustState.TRUSTED_ACTIVE,
        trusted_active_revision_id=revision.revision_id,
        updated_by_principal_id="user_admin",
    )
    return revision.revision_id


async def _seed_family(session) -> str:
    root, _detail, _revision = await rationale_repo.create_family(
        session,
        owner_principal_id="user_admin",
        created_by_principal_id="user_admin",
        display_name="Reversal / Mean Reversion",
        normalized_name="reversal / mean reversion",
        subfamilies=[],
        compatible_output_types=["directional_signal"],
        display_color="#FFD1DC",
        change_note=None,
    )
    return root.entity_id


async def _drive_to_draft(session, *, family_id: str, equivalence_claim: bool | None = None) -> str:
    """Create a TRANSLATE (equivalence-claiming) request and drive it to draft_created."""
    created = await cp_cmd.create_package_request(
        session,
        OWNER,
        package_type="indicator",
        creation_mode=CreationMode.TRANSLATE_EXISTING_CODE,
        source_language=SourceLanguage.PINESCRIPT,
        other_language_label=None,
        target_runtime=RuntimeAdapter.PYTHON,
        request_body="//@version=5\nindicator('rsi')\nta.rsi(close, 14)",
        output_contract=_INDICATOR_OUTPUT,
        rationale_family_id=family_id,
        declared_dependencies=[_RSI_DEP],
        equivalence_claim=equivalence_claim,
    )
    request_id = created["request_id"]
    await cp_cmd.run_precheck(session, OWNER, request_id=request_id)
    sent = await cp_cmd.submit_candidate_generation(session, OWNER, request_id=request_id)
    await cp_cmd.create_draft_from_candidate(
        session, OWNER, request_id=request_id, expected_candidate_hash=sent["candidate_hash"]
    )
    await session.flush()
    return request_id


async def _seed_request_at_draft(session, *, equivalence_claim: bool | None = None) -> str:
    await _seed_principals(session)
    await _seed_python_resolver(session)
    family_id = await _seed_family(session)
    request_id = await _drive_to_draft(
        session, family_id=family_id, equivalence_claim=equivalence_claim
    )
    await session.commit()
    return request_id


async def test_upload_and_parse_happy_path(session, fake_object_store) -> None:
    request_id = await _seed_request_at_draft(session)

    uploaded = await cp_cmd.upload_baseline_asset(
        session,
        OWNER,
        request_id=request_id,
        content=_GOOD_CSV,
        baseline_metadata=_FULL_METADATA,
        original_filename="baseline.csv",
    )
    await session.commit()
    assert uploaded["parse_status"] == str(BaselineParseStatus.UPLOADED)
    assert uploaded["attempt_no"] == 1

    parsed = await cp_cmd.start_baseline_parse(session, OWNER, request_id=request_id)
    await session.commit()
    assert parsed["parse_status"] == str(BaselineParseStatus.PASSED)
    assert parsed["parse_report"]["row_count"] == 2
    assert parsed["parse_report"]["is_parseable"] is True

    detail = await cp_repo.get_request_detail(session, request_id)
    asset = await cp_repo.get_current_baseline_asset(session, detail)
    assert asset is not None
    assert asset.parse_status == BaselineParseStatus.PASSED
    assert asset.parsed_at is not None


async def test_incomplete_metadata_is_rejected(session, fake_object_store) -> None:
    request_id = await _seed_request_at_draft(session)
    await cp_cmd.upload_baseline_asset(
        session,
        OWNER,
        request_id=request_id,
        content=_GOOD_CSV,
        baseline_metadata={"provider": "tradingview", "symbol": "BTCUSDT"},
        original_filename="baseline.csv",
    )
    await session.commit()

    with pytest.raises(BaselineMetadataInvalid):
        await cp_cmd.start_baseline_parse(session, OWNER, request_id=request_id)

    # A rejected parse leaves the upload evidence at `uploaded` (re-upload to fix).
    detail = await cp_repo.get_request_detail(session, request_id)
    asset = await cp_repo.get_current_baseline_asset(session, detail)
    assert asset is not None
    assert asset.parse_status == BaselineParseStatus.UPLOADED


async def test_unparseable_csv_is_rejected(session, fake_object_store) -> None:
    request_id = await _seed_request_at_draft(session)
    await cp_cmd.upload_baseline_asset(
        session,
        OWNER,
        request_id=request_id,
        content=b"time,rsi\n",  # header only, no data rows
        baseline_metadata=_FULL_METADATA,
        original_filename="baseline.csv",
    )
    await session.commit()

    with pytest.raises(BaselineParseFailed):
        await cp_cmd.start_baseline_parse(session, OWNER, request_id=request_id)


async def test_non_csv_upload_is_rejected(session, fake_object_store) -> None:
    request_id = await _seed_request_at_draft(session)
    with pytest.raises(FileTypeNotAllowedError):
        await cp_cmd.upload_baseline_asset(
            session,
            OWNER,
            request_id=request_id,
            content=_GOOD_CSV,
            baseline_metadata=_FULL_METADATA,
            original_filename="baseline.txt",
        )


async def test_parse_without_upload_is_not_found(session, fake_object_store) -> None:
    request_id = await _seed_request_at_draft(session)
    with pytest.raises(BaselineAssetNotFound):
        await cp_cmd.start_baseline_parse(session, OWNER, request_id=request_id)


async def test_equivalence_claim_without_baseline_blocks_approve(
    session, fake_object_store
) -> None:
    request_id = await _seed_request_at_draft(session)  # TRANSLATE -> claims equivalence
    detail = await cp_repo.get_request_detail(session, request_id)
    assert detail is not None and detail.claims_equivalence is True

    await cp_cmd.start_package_validation_run(session, OWNER, request_id=request_id)
    await session.commit()

    # Validation passed but no baseline -> the mode-aware gate refuses publish.
    with pytest.raises(BaselineRequired):
        await cp_cmd.approve_and_publish(session, ADMIN, request_id=request_id)


async def test_equivalence_claim_with_passed_baseline_allows_approve(
    session, fake_object_store
) -> None:
    request_id = await _seed_request_at_draft(session)
    await cp_cmd.upload_baseline_asset(
        session,
        OWNER,
        request_id=request_id,
        content=_GOOD_CSV,
        baseline_metadata=_FULL_METADATA,
        original_filename="baseline.csv",
    )
    await session.commit()
    await cp_cmd.start_baseline_parse(session, OWNER, request_id=request_id)
    await session.commit()
    await cp_cmd.start_package_validation_run(session, OWNER, request_id=request_id)
    await session.commit()

    published = await cp_cmd.approve_and_publish(session, ADMIN, request_id=request_id)
    await session.commit()
    assert published["approval_state"] == str(ApprovalState.APPROVED)
    assert published["visibility_scope"] == str(VisibilityScope.PUBLISHED)


async def test_non_equivalence_request_needs_no_baseline(session, fake_object_store) -> None:
    # Explicit equivalence_claim=False overrides the TRANSLATE default.
    request_id = await _seed_request_at_draft(session, equivalence_claim=False)
    detail = await cp_repo.get_request_detail(session, request_id)
    assert detail is not None and detail.claims_equivalence is False

    await cp_cmd.start_package_validation_run(session, OWNER, request_id=request_id)
    await session.commit()
    published = await cp_cmd.approve_and_publish(session, ADMIN, request_id=request_id)
    await session.commit()
    assert published["approval_state"] == str(ApprovalState.APPROVED)


async def test_reupload_is_a_new_immutable_attempt(session, fake_object_store) -> None:
    request_id = await _seed_request_at_draft(session)
    first = await cp_cmd.upload_baseline_asset(
        session,
        OWNER,
        request_id=request_id,
        content=_GOOD_CSV,
        baseline_metadata=_FULL_METADATA,
        original_filename="baseline.csv",
    )
    await session.commit()
    first_asset = await cp_repo.get_baseline_asset(session, first["baseline_asset_id"])
    assert first_asset is not None
    first_key = first_asset.object_key

    second = await cp_cmd.upload_baseline_asset(
        session,
        OWNER,
        request_id=request_id,
        content=b"time,rsi\n2024-02-01T00:00:00Z,60.0\n",
        baseline_metadata=_FULL_METADATA,
        original_filename="baseline-v2.csv",
    )
    await session.commit()

    assert first["attempt_no"] == 1
    assert second["attempt_no"] == 2
    assert second["baseline_asset_id"] != first["baseline_asset_id"]

    # The first attempt is immutable evidence; the head now points at attempt 2.
    reloaded_first = await cp_repo.get_baseline_asset(session, first["baseline_asset_id"])
    assert reloaded_first is not None
    assert reloaded_first.object_key == first_key
    assert reloaded_first.attempt_no == 1
    detail = await cp_repo.get_request_detail(session, request_id)
    assert detail is not None
    assert detail.baseline_asset_id == second["baseline_asset_id"]
    assert await _count(session, BaselineAsset) == 2


async def test_upload_and_parse_write_audit_events(session, fake_object_store) -> None:
    from entropia.infrastructure.postgres.models import AuditEvent

    request_id = await _seed_request_at_draft(session)

    before = await _count(session, AuditEvent)
    await cp_cmd.upload_baseline_asset(
        session,
        OWNER,
        request_id=request_id,
        content=_GOOD_CSV,
        baseline_metadata=_FULL_METADATA,
        original_filename="baseline.csv",
    )
    await session.commit()
    assert await _count(session, AuditEvent) == before + 1  # baseline_uploaded

    await cp_cmd.start_baseline_parse(session, OWNER, request_id=request_id)
    await session.commit()
    assert await _count(session, AuditEvent) == before + 2  # + baseline_validated


async def test_uploaded_baseline_appears_in_request_projection(session, fake_object_store) -> None:
    from entropia.application.queries import create_package as cp_query

    request_id = await _seed_request_at_draft(session)
    await cp_cmd.upload_baseline_asset(
        session,
        OWNER,
        request_id=request_id,
        content=_GOOD_CSV,
        baseline_metadata=_FULL_METADATA,
        original_filename="baseline.csv",
    )
    await session.commit()
    await cp_cmd.start_baseline_parse(session, OWNER, request_id=request_id)
    await session.commit()

    projection = await cp_query.get_package_request(session, OWNER, request_id=request_id)
    assert projection["claims_equivalence"] is True
    assert projection["baseline_required"] is True
    assert projection["baseline_ready"] is True
    assert projection["current_baseline"]["parse_status"] == str(BaselineParseStatus.PASSED)


async def test_baseline_asset_detail_query(session, fake_object_store) -> None:
    from entropia.application.queries import create_package as cp_query

    request_id = await _seed_request_at_draft(session)
    uploaded: dict[str, Any] = await cp_cmd.upload_baseline_asset(
        session,
        OWNER,
        request_id=request_id,
        content=_GOOD_CSV,
        baseline_metadata=_FULL_METADATA,
        original_filename="baseline.csv",
    )
    await session.commit()

    detail = await cp_query.get_baseline_asset(
        session, OWNER, baseline_asset_id=uploaded["baseline_asset_id"]
    )
    assert detail["request_id"] == request_id
    assert detail["baseline_metadata"]["provider"] == "tradingview"
    assert detail["parse_status"] == str(BaselineParseStatus.UPLOADED)
