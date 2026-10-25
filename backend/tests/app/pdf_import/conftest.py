import pytest

from backend.app.container import container


@pytest.fixture(autouse=True)
async def no_real_ai_provider():
    """Import tests never call a real AI provider; tests that need one install a fake.

    Imports a test started in the background are finished before the
    provider is put back and before the next test: otherwise one could keep
    running into a later test (its database reset, its limits, its timing)
    with the real provider lookup restored."""
    pipeline = container.pdf_import_pipeline()
    previous = pipeline._provider_resolver
    pipeline._provider_resolver = None
    yield pipeline
    try:
        await container.pdf_import_service().wait_for_background_imports()
    finally:
        pipeline._provider_resolver = previous


@pytest.fixture(autouse=True)
def import_in_the_api_process(monkeypatch):
    """These tests follow an import to its end through the API process, as
    ``JOBS_BACKEND__import_form=temporal`` runs it; the default, the job queue
    on Postgres, is a worker's business (tests/app/jobs, and the job body below)."""
    from dataclasses import replace

    from common.db.flags import JobsBackend

    service = container.pdf_import_service()
    flags = replace(service._flags, jobs_overrides={"import_form": JobsBackend.TEMPORAL})
    monkeypatch.setattr(service, "_flags", flags)
