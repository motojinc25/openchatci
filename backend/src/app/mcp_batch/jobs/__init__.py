# Job type registry
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import asyncio

    from app.mcp_batch.models import Job
    from app.mcp_batch.storage import JobStorage

from app.mcp_batch.jobs.rag_ingest import run_rag_ingest_job
from app.mcp_batch.jobs.sleep import run_sleep_job

# Map job_type string -> async job function
JOB_REGISTRY: dict[str, object] = {
    "sleep": run_sleep_job,
    "rag-ingest": run_rag_ingest_job,
}


def get_available_types() -> list[str]:
    """Return list of registered job type names."""
    return list(JOB_REGISTRY.keys())
