from pydantic_settings import BaseSettings, SettingsConfigDict


class PdfImportSettings(BaseSettings):
    """Limits and defaults for importing PDF (or photographed) forms.

    Available on every plan, so the limits are the abuse guard. The sandbox
    limits bound what a hostile PDF can cost the worker that parses it.
    """

    MAX_BYTES: int = 25 * 1024 * 1024
    MAX_PAGES: int = 30
    IMPORTS_PER_WORKSPACE_PER_DAY: int = 10
    CONCURRENT_IMPORTS_PER_WORKSPACE: int = 1
    # a rendered page larger than this is refused (decompression bombs)
    MAX_IMAGE_PIXELS: int = 60_000_000
    SANDBOX_TIMEOUT_S: int = 120
    SANDBOX_MEMORY_MB: int = 1536
    # structuring model used when the workspace's provider is OpenAI
    OPENAI_MODEL: str = "gpt-6-luna"

    model_config = SettingsConfigDict(env_prefix="PDF_IMPORT_")
