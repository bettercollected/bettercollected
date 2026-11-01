"""Isolation of the actions executor's custom action code (docs/executor-isolation.md).

``policy`` (what the code may say), ``confine`` (what the process may do),
``child`` (the process the code runs in) and ``broker`` (the executor's side:
starts the child, answers its calls). Nothing here imports the executor's
settings, keys or database: the child imports only this package and the
standard library.
"""
