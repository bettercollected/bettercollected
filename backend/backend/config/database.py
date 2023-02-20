from pydantic import BaseSettings


class MongoSettings(BaseSettings):
    DB: str = "better_collected_api"
    URI: str = "mongodb://localhost"

    class Config:
        case_sensitive = True
        env_prefix = "MONGO_"
