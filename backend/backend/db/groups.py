"""Repository groups and the order they may be served from Postgres in.

A group's Mongo repositories may ``$lookup`` into another group's collections
(responses → forms, workspace_forms). Once that other group is served from
Postgres the joins find nothing, so it may only cut over after — or together
with — the groups that join into it. ``load_flags`` enforces this map at boot.
"""

READ_DEPENDENCIES = {
    # FormResponseRepository / DeletionRequestsRepository $lookup forms + workspace_forms
    "forms": ("responses",),
}
