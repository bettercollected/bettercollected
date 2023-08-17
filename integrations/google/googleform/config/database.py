from pydantic import BaseSettings


class MongoSettings(BaseSettings):
    DB: str = "bettercollected_googleform"
    URI: str = "mongodb://localhost"

    class Config:
        case_sensitive = True
        env_prefix = "MONGO_"
