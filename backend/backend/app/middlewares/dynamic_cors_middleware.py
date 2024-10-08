import datetime

from common.utils.asyncio_run import asyncio_run
from starlette.middleware.cors import CORSMiddleware

from backend.app.schemas.allowed_origin import AllowedOriginsDocument


class DynamicCORSMiddleware(CORSMiddleware):
    allowedOrigins = []
    time = datetime.datetime.now(datetime.timezone.utc)

    def is_allowed_origin(self, origin: str) -> bool:
        if (
            datetime.datetime.now(datetime.timezone.utc).timestamp()
            < (self.time.timestamp() + float(60 * 60))
            and origin in self.allowedOrigins
        ):
            return True
        origins = asyncio_run(AllowedOriginsDocument.find().to_list())
        all_origins = [o.origin for o in origins]
        self.allowedOrigins = [*all_origins]
        allow = origin in all_origins
        self.time = datetime.datetime.now(datetime.timezone.utc)
        return allow
