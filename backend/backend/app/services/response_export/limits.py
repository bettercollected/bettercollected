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
# a download that did not finish within this long may be started again
DOWNLOAD_CLAIM_TTL = dt.timedelta(minutes=10)
# sweeps: a queued export whose job never got queued, a running one whose worker died
REDEFER_AFTER = dt.timedelta(minutes=2)
STALE_RUNNING_AFTER = dt.timedelta(minutes=30)
MAX_ATTEMPTS = 3
# a streamed export still "streaming" after this long was cut off (the process died)
STALE_STREAMING_AFTER = dt.timedelta(hours=1)
