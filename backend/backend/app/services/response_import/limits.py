"""The limits of the CSV import of responses. Constants, not settings: they are
the product's promise (what is accepted, how long a file waits, who may run)."""

import datetime as dt

# the upload: bytes, data rows, columns, characters of one cell and of a header
MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_ROWS = 5_000
MAX_COLUMNS = 500
MAX_CELL_CHARS = 10_000
MAX_HEADER_CHARS = 200
# responses stored (and rows converted) per step of the job
BATCH_SIZE = 100
# problems listed on the import row (the totals per code are exact)
PROBLEMS_LISTED = 200
# an uploaded file is deleted this long after it was uploaded, at the latest
FILE_TTL = dt.timedelta(hours=1)
# uploads per user and form in a window (the limiter's window)
UPLOADS_PER_WINDOW = 10
WINDOW_SECONDS = 3600
# imports being checked, queued or run per workspace
WORKSPACE_MAX_JOBS = 2
# a running job beats at least this often; one silent for STALE_RUNNING_AFTER is dead
HEARTBEAT_EVERY = dt.timedelta(seconds=20)
STALE_RUNNING_AFTER = dt.timedelta(minutes=15)
# a job that no worker took in this long is failed (``queue_timeout``)
QUEUED_MAX_AGE = dt.timedelta(hours=1)
# a job whose worker died is taken up again this many times, then failed
MAX_ATTEMPTS = 3
# the sweep queues a job that never got queued after this long
REDEFER_AFTER = dt.timedelta(minutes=2)
# an import can be undone this long after it completed
ROLLBACK_WINDOW = dt.timedelta(days=14)
# rows older than this are refused as a date typo (a submission time before it)
OLDEST_SUBMISSION_YEAR = 1990
# the queue the job runs on (the backend's own worker serves it)
IMPORTS_QUEUE = "exports"
