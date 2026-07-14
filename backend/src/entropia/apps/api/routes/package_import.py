"""Package import API (S3, doc 08 §9.1/§10/§14, master ref Modül 7 §12).

Thin handlers: parse body/headers -> resolve actor -> call one command/query. Import
is the reverse of Export: a durable async job returning 202 with a stable import-job
id; the worker actor is dispatched after the request transaction commits. The GET
endpoints read the owner-scoped import projection for the Library Import report.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field

from entropia.application.commands import package_import as import_cmd
from entropia.application.queries import package_import as import_query
from entropia.apps.api.deps import RequestContext, request_context
from entropia.infrastructure.queues import enqueue as job_enqueue

router = APIRouter(tags=["package-import"])


class SubmitPackageImportBody(BaseModel):
    manifest: dict[str, Any] = Field(
        ..., description="An export manifest produced by POST /library/{id}/export."
    )


@router.post("/package-imports", status_code=202)
async def submit_package_import(
    body: SubmitPackageImportBody,
    ctx: RequestContext = Depends(request_context),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    result = await import_cmd.submit_package_import(
        ctx.session,
        ctx.actor,
        manifest=body.manifest,
        idempotency_key=idempotency_key,
    )
    # Dispatch the durable actor after the request tx commits (job row already durable).
    from entropia.apps.worker.actors import run_package_import

    job_enqueue.send_job(run_package_import, result["job_id"])
    return result


@router.get("/package-imports")
async def list_package_imports(
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    return await import_query.list_import_reports(ctx.session, ctx.actor)


@router.get("/package-imports/{import_job_id}")
async def get_package_import(
    import_job_id: str,
    ctx: RequestContext = Depends(request_context),
) -> dict[str, Any]:
    return await import_query.get_import_report(ctx.session, ctx.actor, import_job_id=import_job_id)
