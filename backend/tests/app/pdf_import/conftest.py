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
