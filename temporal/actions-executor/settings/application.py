from dotenv import load_dotenv
from pydantic_settings import BaseSettings

from settings.apm_settings import APMSettings

load_dotenv()


class ApplicationSettings(BaseSettings):
    temporal_server_url: str = "localhost:7233"
    namespace: str = "default"
    server_url: str = "http://backend:8000/api/v1"
    api_key: str = "random_api_key"
    aes_hex_key: str = ""
    worker_queue: str = "actions"
    frontend_url: str = "http://localhost:3000"
    backend_url: str = "http://localhost:8000/api/v1"
    workers: int = 10
    cookie_domain: str = "localhost"
    max_thread_pool_executors: int = 20
    apm_settings: APMSettings = APMSettings()


settings = ApplicationSettings()
