from pydantic import BaseSettings


class ApplicationSettings(BaseSettings):
    server_url: str = "http://backend:8000/api/v1"


settings = ApplicationSettings()
