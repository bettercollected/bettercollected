"""Background jobs on Postgres (procrastinate) — plans/postgres-consolidation.md §7.

Three job kinds exist today (Temporal): ``delete_user``, ``delete_response``
(scheduled at the response's expiration) and ``run_action`` (executed by the
actions-executor process on its own queue). ``JOBS_BACKEND`` / ``JOBS_BACKEND__<job>``
choose, per job kind, whether TemporalService starts a Temporal workflow or
defers a procrastinate job; the default stays ``temporal`` through R1.
"""
