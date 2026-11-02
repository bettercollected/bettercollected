"""Form-level access: grants on a single form, member teams and restricted
forms (docs/enterprise-access-model.md, "Form-level scope"), behind
``FORM_ACCESS_ENABLED``.

``FormAccessService.permissions_on`` is the one place that combines a member's
workspace role, their grants (direct and through teams) and the form's access
mode. Services keep calling ``AuthorizationService.authorize(..., form_id=...)``;
they never read a grant themselves.
"""
