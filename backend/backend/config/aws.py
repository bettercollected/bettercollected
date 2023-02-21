class AWSSettings:
    access_key_id: str = ""
    secret_access_key: str = ""

    class Config:
        env_prefix = "AWS_"
