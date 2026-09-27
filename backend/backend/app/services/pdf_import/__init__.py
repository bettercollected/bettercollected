"""Importing PDF (and photographed) forms into draft forms.

Stages, each checkpointed on the import record so a retried job resumes:

    intake    file type, size, page count, encryption (in the sandbox)
    analyze   per-page signals and the route each page is read by (in the sandbox)
    …         extraction, structuring and compilation stages follow

Untrusted documents are only ever opened inside ``sandbox`` (a subprocess
with memory and CPU limits), never in the API or worker process itself.
"""
