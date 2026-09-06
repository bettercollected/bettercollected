"""Repository groups and the order they may leave Mongo in.

A group's Mongo repositories may ``$lookup`` into another group's collections.
Such a join finds nothing once the joined group stops writing Mongo, so while
the joining group still reads from Mongo, the joined groups must keep writing
it (``dual`` / ``postgres_primary_dual``). ``load_flags`` enforces the map at
boot; the Postgres twins compose over routed repositories instead of joining,
so a group served from Postgres frees the groups it used to join into.
"""

MONGO_JOINS = {
    # FormResponseRepository / DeletionRequestsRepository → forms, workspace_forms
    "responses": ("forms",),
    # FormTemplateRepository.get_templates_with_creator → workspaces
    "forms": ("identity",),
    # WorkspaceRepository.get_workspace_with_action_by_id → workspace_actions
    "identity": ("actions",),
}
