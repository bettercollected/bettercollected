import pytest

from backend.app.container import container


@pytest.fixture(autouse=True)
def no_real_ai_provider():
    """Import tests never call a real AI provider; tests that need one install a fake."""
    pipeline = container.pdf_import_pipeline()
    previous = pipeline._provider_resolver
    pipeline._provider_resolver = None
    yield pipeline
    pipeline._provider_resolver = previous
