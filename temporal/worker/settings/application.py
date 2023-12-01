from dotenv import load_dotenv
from pydantic import BaseSettings

from settings.apm_settings import APMSettings

load_dotenv()


class ApplicationSettings(BaseSettings):
    temporal_server_url: str = "localhost:7233"
    namespace: str = "default"
    server_url: str = "http://backend:8000/api/v1"
    api_key: str = "random_api_key"
    aes_hex_key: str = ""
    worker_queue: str = "default"
    workers: int = 10
    cookie_domain: str = "localhost"
    apm_settings: APMSettings = APMSettings()


settings = ApplicationSettings()
