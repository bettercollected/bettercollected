"""Background jobs on Postgres (procrastinate) — plans/postgres-consolidation.md §7.

Job kinds: ``delete_user``, ``delete_response`` (scheduled at the response's
expiration), ``run_action`` (executed by the actions-executor process on its own
queue), ``import_form`` and the two queue-only jobs. ``JOBS_BACKEND`` /
``JOBS_BACKEND__<job>`` choose, per job kind, whether TemporalService starts a
Temporal workflow or defers a procrastinate job; the default is ``postgres``
since 4.1.
"""
