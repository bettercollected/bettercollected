"""Limits of the import. The archive is untrusted: every one of these is
enforced while reading (never from sizes the archive declares)."""

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
# the six files of an export, plus room for a few extras that are ignored
MAX_ENTRIES = 16
# size of the central directory we let the zip reader parse (it parses every
# record it holds before we can count them): sixteen records are far smaller
MAX_CENTRAL_DIRECTORY_BYTES = 16 * 1024
MAX_ENTRY_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BYTES = 16 * 1024 * 1024
MAX_ENTRY_NAME_LENGTH = 255
READ_CHUNK = 64 * 1024

MAX_JSON_DEPTH = 64
MAX_JSON_NODES = 400_000

# what one form may hold before we refuse it as too complex (before the
# form's own size limits, MAX_PAGES / MAX_FIELDS, would)
MAX_STEPS = 100
MAX_COMPONENTS = 2000
MAX_COMPONENT_DEPTH = 12
MAX_CHOICES = 200
MAX_LOGIC_RULES = 500
MAX_VARIABLES = 1000

# text limits (characters)
MAX_TITLE = 500
MAX_HELP = 1000
MAX_STATEMENT = 5000
MAX_CHOICE = 300
MAX_LABEL_IN_REPORT = 200
MAX_KEY_IN_REPORT = 120
MAX_PATTERN = 500

MAX_REPORT_ITEMS = 500

# the series of Open Formulieren releases we read (MAJOR.MINOR)
ACCEPTED_SERIES = ((4, 0),)

# one import may process this many characters of text and run this long
# (seconds, wall clock) before it is refused as too complex
MAX_TEXT_CHARS = 1_500_000
BUILD_SECONDS = 5.0
# imports running at once in this process (more: 503 import_busy)
MAX_CONCURRENT_IMPORTS = 2
# number parsing: anything longer or larger is not a number we use
MAX_NUMBER_TEXT = 64
MAX_NUMBER_VALUE = 10**15
# parts of a multipart upload we look at (one file is all we need)
MAX_UPLOAD_PARTS = 4
