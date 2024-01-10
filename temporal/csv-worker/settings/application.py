from dotenv import load_dotenv
from pydantic.v1 import BaseSettings

from settings.apm_settings import APMSettings

load_dotenv()


class ApplicationSettings(BaseSettings):
    smtp_username: str = ''
    smtp_password: str = ''
    smtp_server: str = ''
    smtp_port: int = 587
    smtp_sender: str = ''
    aws_access_key_id: str = ''
    aws_secret_access_key: str = ''
    region_name: str = ''
    endpoint_url: str = ''
    temporal_server_url: str = "localhost:7233"
    bucket_name: str = ''
    namespace: str = "default"
    server_url: str = "http://backend:8000/api/v1"
    api_key: str = "random_api_key"
    aes_hex_key: str = ""
    worker_queue: str = "default"
    workers: int = 10
    cookie_domain: str = "localhost"
    max_thread_pool_executors: int = 20
    expiration_time: int = 604800
    apm_settings: APMSettings = APMSettings()


settings = ApplicationSettings()
