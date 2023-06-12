from pydantic import BaseSettings


class MongoSettings(BaseSettings):
    DB: str = "bettercollected_backend"
    URI: str = "mongodb://localhost"

    class Config:
        case_sensitive = True
        env_prefix = "MONGO_"
