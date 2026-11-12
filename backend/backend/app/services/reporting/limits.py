"""The limits of reports on a form's answers. Constants, not settings: they are
the product's promise (how many responses one query reads, how big a definition
may be), the way the export's are (``services/response_export/limits.py``)."""

from backend.app.services.response_export import limits as export_limits

# Most responses one query that needs answers reads. Above it the query is
# refused with the count (413 ``too_many_rows``): a bar chart of the first part
# of the responses is a wrong chart, so no partial result is ever returned.
# Measured in the P1 benchmark (docs/reporting.md): the pass decrypts and
# accumulates this many responses well inside the interactive budget.
REPORT_MAX_ROWS = 20_000
# responses decrypted per read: the export's batch
BATCH_SIZE = export_limits.BATCH_SIZE

# one definition: its size once serialised, its cards, the measures of a card
DEFINITION_MAX_BYTES = 16 * 1024
CARDS_MAX = 24
MEASURES_MAX = 5
TITLE_MAX = 80
CARD_ID_MAX = 64
FORM_VERSIONS_MAX = 50

# One dimension keeps at most this many distinct groups while it counts; beyond
# it a response is counted in the "other groups" total, and the card says it was
# cut (``truncated``).
GROUPS_KEPT_MAX = 1_000
# A dimension that is not a time series returns at most this many groups (the
# biggest by count); the rest are summed in ``otherGroups``.
GROUPS_RETURNED_MAX = 100
# how many cut-off group keys are remembered to say how many were cut
GROUPS_CUT_TRACKED_MAX = 100_000

# queries per user and form in a window (the shared limiter): 429 ``rate_limited``
REQUESTS_PER_WINDOW = 30
WINDOW_SECONDS = 60
# passes over the answers running at once in one process (each decrypts 500
# responses at a time), and how long a request waits for a free one before it
# is told to come back (429 ``report_busy``)
PASSES_AT_ONCE = 2
PASS_WAIT_SECONDS = 2.0
# ...and across every replica: passes in flight in all processes together, kept
# as a counter of the shared rate limiter (``report-passes``). A pass takes a
# place for ``PASS_SLOTS_WINDOW_SECONDS`` at most: it gives it back when it ends,
# and a process that dies in the middle of one loses it with the window, so a
# crash cannot hold a place for good. A pass that straddles two windows is
# counted in the first and given back from the second, so the figure is a close
# bound on the fleet, not an exact one; the per-process limit above stays the
# exact guard of one process.
PASSES_ACROSS_REPLICAS = 6
PASS_SLOTS_WINDOW_SECONDS = 60
# the longest one pass may run before it is stopped (503 ``report_timeout``): a
# 20,000-response pass takes about 2.5 s, so this is a stuck or starved one. It
# is under the slot window, so a stopped pass has always given its place back
# in the window it took it.
PASS_SECONDS = 30.0

# the in-process cache of aggregates (never rows, never answers): entries, and
# a ceiling on how long one lives whatever its token says (bounds memory)
CACHE_SIZE = 128
CACHE_SECONDS = 600.0
# the form's catalogue (built from the draft and every published version), keyed
# by the form's revision
CATALOGUE_CACHE_SIZE = 64
