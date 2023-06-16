from dotenv import load_dotenv
from pydantic import BaseSettings

load_dotenv()


class ApplicationSettings(BaseSettings):
    server_url: str = "http://backend:8000/api/v1"


settings = ApplicationSettings()
