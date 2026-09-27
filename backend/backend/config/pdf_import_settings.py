from pydantic_settings import BaseSettings, SettingsConfigDict


class PdfImportSettings(BaseSettings):
    """Limits and defaults for importing PDF (or photographed) forms.

    Available on every plan, so the limits are the abuse guard. The sandbox
    limits bound what a hostile PDF can cost the worker that parses it.
    """

    # matches the proxy's body limit on /api/v1 (client_max_body_size 15M), so an
    # oversized upload gets our message instead of the proxy's 413 page
    MAX_BYTES: int = 15 * 1024 * 1024
    MAX_PAGES: int = 30
    IMPORTS_PER_WORKSPACE_PER_DAY: int = 10
    CONCURRENT_IMPORTS_PER_WORKSPACE: int = 1
    # a rendered page larger than this is refused (decompression bombs)
    MAX_IMAGE_PIXELS: int = 60_000_000
    SANDBOX_TIMEOUT_S: int = 120
    SANDBOX_MEMORY_MB: int = 1536
    # sandbox children running at once in one process, across all workspaces
    MAX_PARALLEL_SANDBOXES: int = 2
    # the most output the parent reads from one sandbox child: the parent has no
    # memory limit of its own, so a document's result must not be able to exhaust it
    MAX_RESULT_BYTES: int = 16 * 1024 * 1024
    # the isolated document-sandbox container's socket (#703); empty = local child
    SANDBOX_SOCKET: str = ""
    # refuse the local child transport (set wherever the container is deployed)
    REQUIRE_ISOLATED_SANDBOX: bool = False
    # structuring model when the provider is OpenAI (others use their configured model)
    OPENAI_MODEL: str = "gpt-6-luna"
    # longest side of a rendered page image sent to the model (pixels)
    RENDER_MAX_SIDE: int = 1600

    model_config = SettingsConfigDict(env_prefix="PDF_IMPORT_")
