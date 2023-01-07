from pydantic import BaseSettings


class MongoSettings(BaseSettings):
    """
    A class for storing MongoDB settings.

    This class inherits from BaseSettings and defines the db and
    uri attributes for the database name and connection URI,
    respectively. The Config inner class specifies that environment
    variables should be prefixed with "MONGO_" when loading the
    settings.
    """

    db: str = "better_collected_schedulers_db"
    uri: str = ""

    class Config:
        env_prefix = "MONGO_"
