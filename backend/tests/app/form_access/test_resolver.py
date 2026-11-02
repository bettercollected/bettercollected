"""The decision table of form-level access (``resolve``): role union, what a
grant gives and caps, restricted forms, the creator, Owners and Admins, the
Privacy officer, and everything that must stay nothing. Pure: no database."""

import pytest
from common.ids import RecordId

from backend.app.models.enum.permission import Permission
from backend.app.schemas.form_access_grant import (
    GRANT_ROLES,
    ROLE_EDITOR,
    ROLE_REVIEWER,
    ROLE_VIEWER,
    FormAccessGrantDocument,
)
from backend.app.services.authorization_service import (
    ADMIN_PERMISSIONS,
    ALL_PERMISSIONS,
    EDITOR_PERMISSIONS,
    PRIVACY_OFFICER_PERMISSIONS,
    REVIEWER_PERMISSIONS,
    VIEWER_PERMISSIONS,
    permissions_for,
)
from backend.app.services.form_access.model import (
    FORM_SCOPED,
    GRANT_PERMISSIONS,
    MODE_RESTRICTED,
    MODE_WORKSPACE,
    SOURCE_CREATOR,
    SOURCE_GRANT,
    SOURCE_NONE,
    SOURCE_ROLE,
    BaseAccess,
    grant_permissions,
    is_restricted,
    resolve,
)

P = Permission
NO = frozenset()

# The table of docs/enterprise-access-model.md, written out independently of the
# module's constants (a grant never deletes a form, and exports only through
# the Editor role or the export flag).
EDITOR_GRANT = {
    P.FORM_READ,
    P.FORM_EDIT,
    P.FORM_SHARE,
    P.RESPONSE_READ,
    P.RESPONSE_ANNOTATE,
    P.RESPONSE_EXPORT,
    P.RESPONSE_DELETE,
    P.RESPONSE_EDIT,
    P.ANALYTICS_READ,
}
REVIEWER_GRANT = {P.FORM_READ, P.RESPONSE_READ, P.RESPONSE_ANNOTATE, P.ANALYTICS_READ}
VIEWER_GRANT = {P.FORM_READ, P.RESPONSE_READ, P.ANALYTICS_READ}


def grant(role, export=False, subject="user"):
    return FormAccessGrantDocument(
        workspace_id=RecordId(),
        form_id="f" * 24,
        subject_type=subject,
        subject_id="u1",
        role=role,
        export=export,
    )


def member(*roles, **flags) -> BaseAccess:
    """A base access as AuthorizationService builds it for a member holding
    ``roles`` (stored spellings)."""
    return BaseAccess(
        user_id="u1",
        workspace_id="w1",
        permissions=permissions_for(list(roles), is_owner=False),
        privileged=bool({"OWNER", "ADMIN"} & set(roles)),
        privacy_officer="PRIVACY_OFFICER" in roles,
        **flags,
    )


def decide(base, *, restricted=False, creator=False, grants=()):
    return resolve(base, restricted=restricted, creator=creator, grants=grants)


# -- what a grant gives -----------------------------------------------------------
def test_each_grant_role_gives_exactly_its_documented_set():
    assert GRANT_PERMISSIONS[ROLE_EDITOR] == EDITOR_GRANT
    assert GRANT_PERMISSIONS[ROLE_REVIEWER] == REVIEWER_GRANT
    assert GRANT_PERMISSIONS[ROLE_VIEWER] == VIEWER_GRANT
    assert set(GRANT_PERMISSIONS) == set(GRANT_ROLES)


def test_a_grant_only_ever_gives_form_scoped_permissions():
    for role, given in GRANT_PERMISSIONS.items():
        assert given <= FORM_SCOPED, role
    for workspace_level in (
        P.WORKSPACE_MANAGE,
        P.WORKSPACE_BILLING,
        P.MEMBERS_MANAGE,
        P.SECURITY_MANAGE,
        P.AI_MANAGE,
        P.AUDIT_READ,
        P.PRIVACY_MANAGE,
        P.FORM_CREATE,
        P.RESPONSE_IMPORT,
    ):
        assert workspace_level not in FORM_SCOPED


def test_a_grant_never_deletes_the_form():
    for role in GRANT_ROLES:
        assert P.FORM_DELETE not in grant_permissions([grant(role, export=True)])


@pytest.mark.parametrize("role", [ROLE_REVIEWER, ROLE_VIEWER])
def test_export_is_a_flag_on_reviewer_and_viewer_grants(role):
    assert P.RESPONSE_EXPORT not in grant_permissions([grant(role)])
    assert P.RESPONSE_EXPORT in grant_permissions([grant(role, export=True)])


def test_the_export_flag_applies_per_grant_not_across_grants():
    """Two grants (a person and a team): the one without the flag does not
    borrow the other's; the union simply holds both."""
    plain, flagged = grant(ROLE_VIEWER), grant(ROLE_REVIEWER, export=True)
    assert P.RESPONSE_EXPORT not in grant_permissions([plain])
    assert grant_permissions([plain, flagged]) == REVIEWER_GRANT | {P.RESPONSE_EXPORT}


def test_an_editor_grant_exports_without_the_flag_and_the_flag_adds_nothing_else():
    assert grant_permissions([grant(ROLE_EDITOR)]) == EDITOR_GRANT
    assert grant_permissions([grant(ROLE_EDITOR, export=True)]) == EDITOR_GRANT


@pytest.mark.parametrize("role", ["", "OWNER", "ADMIN", "GUEST", "viewer", "COLLABORATOR"])
def test_a_grant_role_this_code_does_not_know_gives_nothing(role):
    assert grant_permissions([grant(role, export=True)]) == NO


def test_grants_add_up():
    assert grant_permissions([grant(ROLE_VIEWER), grant(ROLE_REVIEWER)]) == (
        REVIEWER_GRANT
    )
    assert grant_permissions([]) == NO


# -- the mode ----------------------------------------------------------------------
@pytest.mark.parametrize(
    "mode, hidden, expected",
    [
        (None, None, False),
        (None, False, False),
        (None, True, True),  # Private, no explicit mode: restricted
        (MODE_WORKSPACE, True, False),  # an explicit mode always wins
        (MODE_WORKSPACE, False, False),
        (MODE_RESTRICTED, False, True),
        (MODE_RESTRICTED, True, True),
        ("invite_only", False, True),  # a value from a newer release: closed, never open
        ("", False, True),
    ],
)
def test_is_restricted(mode, hidden, expected):
    assert is_restricted(mode, hidden) is expected


# -- an open form ------------------------------------------------------------------
def test_without_a_grant_an_open_form_is_the_role():
    for roles in (["VIEWER"], ["REVIEWER"], ["EDITOR"], ["COLLABORATOR"], ["PRIVACY_OFFICER"]):
        base = member(*roles)
        decided = decide(base)
        assert decided.permissions == base.permissions
        assert decided.source == SOURCE_ROLE
        assert not decided.hidden and not decided.restricted


def test_a_grant_raises_a_role_on_one_form_and_the_role_is_kept():
    viewer = member("VIEWER")
    decided = decide(viewer, grants=[grant(ROLE_EDITOR)])
    assert decided.permissions == VIEWER_PERMISSIONS | EDITOR_GRANT
    assert decided.source == SOURCE_GRANT
    # what a role gives is never taken away by a smaller grant
    editor = member("EDITOR")
    smaller = decide(editor, grants=[grant(ROLE_VIEWER)])
    assert smaller.permissions == EDITOR_PERMISSIONS
    assert smaller.source == SOURCE_ROLE  # the grant added nothing


def test_roles_union_then_grants():
    base = member("VIEWER", "REVIEWER")
    assert decide(base).permissions == REVIEWER_PERMISSIONS
    assert decide(base, grants=[grant(ROLE_EDITOR)]).permissions == (
        REVIEWER_PERMISSIONS | EDITOR_GRANT
    )


def test_a_viewer_with_an_export_flagged_grant_exports_on_that_form():
    decided = decide(member("VIEWER"), grants=[grant(ROLE_VIEWER, export=True)])
    assert P.RESPONSE_EXPORT in decided.permissions
    assert decided.permissions - VIEWER_PERMISSIONS == {P.RESPONSE_EXPORT}


def test_a_grant_never_raises_a_workspace_level_permission():
    decided = decide(member("VIEWER"), grants=[grant(ROLE_EDITOR, export=True)])
    assert decided.permissions & {
        P.WORKSPACE_MANAGE,
        P.MEMBERS_MANAGE,
        P.SECURITY_MANAGE,
        P.AI_MANAGE,
        P.AUDIT_READ,
        P.PRIVACY_MANAGE,
        P.FORM_CREATE,
        P.RESPONSE_IMPORT,
        P.FORM_DELETE,
    } == NO


# -- a restricted form --------------------------------------------------------------
@pytest.mark.parametrize("roles", [["VIEWER"], ["REVIEWER"], ["EDITOR"], ["COLLABORATOR"], []])
def test_a_restricted_form_closes_every_form_scoped_permission_without_a_way_in(roles):
    base = member(*roles)
    decided = decide(base, restricted=True)
    assert decided.permissions & FORM_SCOPED == NO
    assert decided.source == SOURCE_NONE
    assert decided.hidden  # they held form.read through the role: unknown form to them
    # what is not about a form stays (an Editor can still create forms)
    assert decided.permissions == base.permissions - FORM_SCOPED


def test_restricted_with_a_grant_gives_what_the_grant_gives_not_the_role():
    decided = decide(member("EDITOR"), restricted=True, grants=[grant(ROLE_VIEWER)])
    assert decided.permissions & FORM_SCOPED == VIEWER_GRANT
    assert decided.source == SOURCE_GRANT
    assert not decided.hidden
    # the Editor role's reach does not leak through on a restricted form
    assert P.FORM_EDIT not in decided.permissions
    assert P.RESPONSE_EXPORT not in decided.permissions
    # but what is about the workspace is still theirs
    assert P.FORM_CREATE in decided.permissions


@pytest.mark.parametrize(
    "role, given", [(ROLE_EDITOR, EDITOR_GRANT), (ROLE_REVIEWER, REVIEWER_GRANT), (ROLE_VIEWER, VIEWER_GRANT)]
)
def test_each_grant_role_on_a_restricted_form(role, given):
    decided = decide(member("VIEWER"), restricted=True, grants=[grant(role)])
    assert decided.permissions & FORM_SCOPED == given


def test_two_grants_on_a_restricted_form_take_the_union():
    decided = decide(
        member("VIEWER"),
        restricted=True,
        grants=[grant(ROLE_VIEWER, export=True), grant(ROLE_REVIEWER, subject="group")],
    )
    assert decided.permissions & FORM_SCOPED == REVIEWER_GRANT | {P.RESPONSE_EXPORT}


def test_the_creator_keeps_their_own_roles_permissions_and_no_more():
    """Decision 13: the creator rule is not an elevation. A demoted creator
    keeps what their current role gives on their own form."""
    for roles in (["EDITOR"], ["VIEWER"], ["REVIEWER"]):
        base = member(*roles)
        decided = decide(base, restricted=True, creator=True)
        assert decided.permissions == base.permissions
        assert decided.source == SOURCE_CREATOR
        assert not decided.hidden
    viewer_creator = decide(member("VIEWER"), restricted=True, creator=True)
    assert P.FORM_EDIT not in viewer_creator.permissions
    assert P.RESPONSE_EXPORT not in viewer_creator.permissions


def test_a_creator_who_also_holds_a_grant_gets_both():
    decided = decide(
        member("VIEWER"), restricted=True, creator=True, grants=[grant(ROLE_EDITOR)]
    )
    assert decided.permissions == VIEWER_PERMISSIONS | EDITOR_GRANT


def test_being_the_creator_changes_nothing_on_an_open_form():
    base = member("VIEWER")
    assert decide(base, creator=True).permissions == base.permissions


# -- owners and admins ---------------------------------------------------------------
@pytest.mark.parametrize("roles, held", [(["OWNER"], ALL_PERMISSIONS), (["ADMIN"], ADMIN_PERMISSIONS)])
def test_owners_and_admins_always_pass_whatever_the_form_says(roles, held):
    base = member(*roles)
    assert base.permissions == held
    for restricted in (False, True):
        for creator in (False, True):
            decided = decide(base, restricted=restricted, creator=creator)
            assert decided.permissions == held
            assert not decided.hidden


def test_an_admin_with_a_smaller_grant_is_still_an_admin():
    decided = decide(member("ADMIN"), restricted=True, grants=[grant(ROLE_VIEWER)])
    assert decided.permissions == ADMIN_PERMISSIONS


# -- the privacy officer ---------------------------------------------------------------
def test_a_grant_never_elevates_a_privacy_officer():
    base = member("PRIVACY_OFFICER")
    for restricted in (False, True):
        decided = decide(base, restricted=restricted, grants=[grant(ROLE_EDITOR, export=True)])
        assert decided.permissions & {
            P.RESPONSE_READ,
            P.RESPONSE_ANNOTATE,
            P.RESPONSE_EXPORT,
            P.RESPONSE_EDIT,
            P.FORM_EDIT,
        } == NO


def test_a_privacy_officer_keeps_structure_and_privacy_on_a_restricted_form():
    decided = decide(member("PRIVACY_OFFICER"), restricted=True)
    assert decided.permissions == {P.FORM_READ, P.PRIVACY_MANAGE, P.AUDIT_READ}
    assert not decided.hidden  # their list still shows the form
    assert P.ANALYTICS_READ in PRIVACY_OFFICER_PERMISSIONS  # on an open form it is theirs
    assert P.ANALYTICS_READ not in decided.permissions  # on a restricted one it is not


def test_a_privacy_officer_on_an_open_form_is_just_their_role():
    base = member("PRIVACY_OFFICER")
    assert decide(base).permissions == PRIVACY_OFFICER_PERMISSIONS


@pytest.mark.parametrize("other", ["EDITOR", "REVIEWER", "VIEWER"])
def test_a_privacy_officer_with_another_role_is_not_elevated_either(other):
    base = member("PRIVACY_OFFICER", other)
    decided = decide(base, restricted=False, grants=[grant(ROLE_EDITOR)])
    assert decided.permissions == base.permissions
    assert P.RESPONSE_READ not in decided.permissions


# -- nothing stays nothing --------------------------------------------------------------
@pytest.mark.parametrize("restricted", [False, True])
@pytest.mark.parametrize("creator", [False, True])
def test_no_access_at_the_base_is_never_turned_into_access(restricted, creator):
    """Not a member, a disabled membership, a blocked session (single sign-on,
    authenticator app) or a role this code does not know: the base is empty."""
    nobody = BaseAccess(user_id="u1", workspace_id="w1", permissions=NO)
    decided = decide(
        nobody,
        restricted=restricted,
        creator=creator,
        grants=[grant(ROLE_EDITOR, export=True)],
    )
    assert decided.permissions == NO
    assert not decided.hidden


def test_a_disabled_workspace_is_not_elevated_by_grants_or_closed_further():
    """Only owners keep their read-only set there, whatever the grants say."""
    owner = BaseAccess(
        user_id="u1",
        workspace_id="w1",
        permissions=frozenset({P.FORM_READ, P.RESPONSE_READ}),
        privileged=True,
        workspace_disabled=True,
    )
    assert decide(owner, restricted=True).permissions == owner.permissions
    member_in_disabled = BaseAccess(
        user_id="u1", workspace_id="w1", permissions=NO, workspace_disabled=True
    )
    assert decide(member_in_disabled, grants=[grant(ROLE_EDITOR)]).permissions == NO
    # even a base that somehow held something is returned as it is
    held = BaseAccess(
        user_id="u1",
        workspace_id="w1",
        permissions=VIEWER_PERMISSIONS,
        workspace_disabled=True,
    )
    assert decide(held, grants=[grant(ROLE_EDITOR)]).permissions == VIEWER_PERMISSIONS


def test_the_reserved_field_rules_slot_is_empty():
    assert decide(member("EDITOR")).field_rules is None
