import pydantic
from dotenv import load_dotenv

from settings.apm_settings import APMSettings

load_dotenv()


class ApplicationSettings(pydantic.BaseSettings):
    temporal_server_url: str = "localhost:7233"
    namespace: str = "default"
    server_url: str = "http://backend:8000/api/v1"
    api_key: str = "random_api_key"
    aes_hex_key: str = ""
    worker_queue: str = "actions"
    workers: int = 10
    cookie_domain: str = "localhost"
    max_thread_pool_executors: int = 20
    apm_settings: APMSettings = APMSettings()


settings = ApplicationSettings()
