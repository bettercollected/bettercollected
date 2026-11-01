"""The limits of the responses export. Constants, not settings: they are the
product's promise (what streams, what runs as a job, how long a file lives)."""

import datetime as dt

# up to this many matching responses the CSV streams in the response itself
# and nothing is stored; above it, a background job builds the file
STREAM_MAX_ROWS = 5_000
# most responses one export holds; more asks to narrow the filters
MAX_ROWS = 100_000
# responses decrypted per read
BATCH_SIZE = 500
# plaintext bytes per stored chunk of a job's file
CHUNK_BYTES = 256 * 1024
# most bytes one job's file may hold
MAX_FILE_BYTES = 256 * 1024 * 1024
# a job's file is deleted this long after it was built, at the latest
FILE_TTL = dt.timedelta(hours=24)
# export requests per user and form in a window (the limiter's window)
REQUESTS_PER_WINDOW = 10
WINDOW_SECONDS = 3600
# sweeps: a queued export whose job never got queued, a running one whose worker died
REDEFER_AFTER = dt.timedelta(minutes=2)
# a running job that has not beaten (``heartbeat_at``) for this long is dead
STALE_RUNNING_AFTER = dt.timedelta(minutes=30)
# a running job beats at least this often, also while it reads rows without
# having a chunk to store yet
HEARTBEAT_EVERY = dt.timedelta(seconds=30)
# a job that has waited this long without a worker taking it is failed
# (``queue_timeout``): without it a missing ``exports`` worker would hold the
# workspace's slots and the sealed filters for ever
QUEUED_MAX_AGE = dt.timedelta(hours=2)
MAX_ATTEMPTS = 3
# a streamed export still "streaming" after this long was cut off (the process died)
STALE_STREAMING_AFTER = dt.timedelta(hours=1)
# jobs in flight (queued or running) per workspace; more wait for these to end
WORKSPACE_MAX_JOBS = 3
# streamed exports (and bulk JSON reads) in flight at once, per requester and
# workspace and per workspace: each holds a response open and decrypts 500 rows
# at a time, so they are counted in Postgres (every backend replica sees the same)
STREAMS_PER_USER = 2
STREAMS_PER_WORKSPACE = 6
# a stream counts toward those limits for this long at most: one whose client
# vanished before the body started never closes its row (the sweep ends it after
# ``STALE_STREAMING_AFTER``), and must not lock its requester out meanwhile
STREAM_SLOT_TTL = dt.timedelta(minutes=15)
# most responses the bulk JSON read (GET .../all-submissions) builds in memory;
# a bigger form is read with an export (POST .../exports: streamed, or a job)
BULK_JSON_MAX_ROWS = 5_000
# a failed or cancelled job is shown to its requester for this long
FAILURE_NEWS_FOR = dt.timedelta(hours=24)
# export jobs have a queue of their own, so they cannot hold up deletions
EXPORTS_QUEUE = "exports"
