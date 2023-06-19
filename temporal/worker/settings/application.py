from dotenv import load_dotenv
from pydantic import BaseSettings

load_dotenv()


class ApplicationSettings(BaseSettings):
    temporal_server_url: str = "localhost:7233"
    namespace: str = "default"
    server_url: str = "http://backend:8000/api/v1"
    api_key: str = "random_api_key"
    aes_hex_key: str = ""


settings = ApplicationSettings()
