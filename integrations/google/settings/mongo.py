from pydantic import BaseSettings


class MongoSettings(BaseSettings):
    db: str = "better_collected_schedulers_db"
    uri: str = ""

    class Config:
        env_prefix = "MONGO_"
