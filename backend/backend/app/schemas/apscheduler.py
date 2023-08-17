from common.configs.mongo_document import MongoDocument


class APSchedulerDocument(MongoDocument):
    id: str
    next_run_time: float
    job_state: bytes

    class Settings:
        name = "jobs"
