"""The forms group's repositories: Postgres only (its Mongo collections are
read only by the import from 4.0, ``python -m backend.migrate``).

Forms and their published versions, the workspace links of forms, templates,
media libraries, workspace consents and PDF imports. Queries use the spine
columns of the rows in :mod:`backend.db.models`; the documents are
:class:`common.records.Record` classes, encoded and decoded by
:mod:`common.records.codec`. The methods keep the behaviour of the 4.0 Mongo
repositories they replace, including their quirks.

The 4.0 aggregation pipelines' ``$lookup``s fall into two kinds
(plans/postgres-consolidation.md §4):

* **within the group** (forms ⋈ workspace_forms ⋈ form_versions) are SQL
  joins on the spine columns;
* **into another group** (responder groups, response and deletion-request
  counts in ``responses``; the workspace a template was imported from in
  ``identity``) are *composed*: the repository reads its own tables, then asks
  the other group's repository in one batched call. The responses group's
  repositories read forms the same way (``response_scope.form_titles``): no
  query joins into another group's tables.

Results keep the raw-document shape of the aggregations (``FormDtoCamelModel``
and friends consume dicts), rebuilt from the row's canonical ``doc``.
"""

from datetime import datetime, timezone
from http import HTTPStatus
from typing import Any, Dict, Iterable, List, Optional, Sequence

from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import apaginate
from sqlalchemy import and_, exists, func, not_, or_, select, text, true, update
from sqlalchemy.exc import DBAPIError, IntegrityError, SQLAlchemyError

from backend.app.exceptions import HTTPException
from backend.app.models.dtos.consent import ConsentCamelModel
from backend.app.models.dtos.form_actions_dto import FormActionsDto
from backend.app.models.enum.FormVersion import FormVersion
from backend.app.models.filter_queries.sort import SortOrder, SortRequest
from backend.app.models.template import StandardFormTemplate, StandardTemplateSetting
from backend.app.models.workspace import WorkspaceFormSettings
from backend.app.schemas.consent import WorkspaceConsentDocument
from backend.app.services.form_concurrency import (
    ensure_not_changed_since,
    form_changed,
    next_updated_at,
)
from backend.app.repositories.response_scope import ResponseScope
from backend.app.repositories.metric_periods import (
    object_id_at,
    postgres_counts_per_period,
)
from backend.app.schemas.form_import import FormImportDocument, ImportStatus
from backend.app.schemas.form_versions import FormVersionsDocument
from backend.app.schemas.media_library import MediaLibraryDocument
from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.template import FormTemplateDocument
from backend.app.schemas.workspace_form import WorkspaceFormDocument
from backend.db.base import SCHEMA
from backend.db.models import (
    FormImportRow,
    FormRow,
    FormTemplateRow,
    FormVersionRow,
    MediaLibraryRow,
    WorkspaceConsentRow,
    WorkspaceFormRow,
)
from common.constants import MESSAGE_DATABASE_EXCEPTION, MESSAGE_NOT_FOUND
from common.records import RecordId, decode, from_canonical_document, row_values
from common.records.repository import RecordRepository
from common.models.standard_form import ParameterValue, StandardForm, Trigger
from common.models.user import User
from common.clock import utcnow


# -- rules shared by the repositories below (and the services) -----------------
def apply_form_update(form_document: FormDocument, form: StandardForm) -> None:
    """Copy a whole-form save onto the stored draft (both stores)."""
    form_document.fields = form.fields
    # None means "the client didn't send hidden fields" (e.g. an older
    # webapp bundle) — preserve what's stored. An explicit [] clears them.
    if form.hidden_fields is not None:
        form_document.hidden_fields = form.hidden_fields
    form_document.title = form.title
    form_document.logo = form.logo
    form_document.cover_image = form.cover_image
    form_document.description = form.description
    form_document.welcome_page = form.welcome_page
    form_document.thankyou_page = form.thankyou_page
    form_document.theme = form.theme
    # The logo settings: None means "not sent" (an older client); keep them.
    for name in ("logo_position", "logo_alt", "use_workspace_logo"):
        if getattr(form, name, None) is not None:
            setattr(form_document, name, getattr(form, name))
    form_document.consent = form.consent if form.consent else form_document.consent
    if form.settings:
        _apply_settings_update(form_document, form.settings)


def _apply_settings_update(form_document: FormDocument, sent) -> None:
    """The settings a whole-form save sends, onto the form's own settings:
    each setting the save gives (``model_fields_set``, null included, which
    clears it); what it leaves out stays. The builder's save gives the
    language alone; a spec replace gives the form's whole settings."""
    if form_document.settings is None:
        form_document.settings = sent
        return
    stored = form_document.settings
    for key in sent.model_fields_set:
        setattr(stored, key, getattr(sent, key))


def detach_action(form: FormDocument, action_id: str) -> None:
    """Drop one action from a form's triggers, parameters and secrets, in
    place; every other action keeps its own (the repository applies it to
    rows it holds locked)."""
    for trigger, states in (form.actions or {}).items():
        form.actions[trigger] = [s for s in states or [] if str(s.id) != action_id]
    for bag in (form.parameters, form.secrets):
        if isinstance(bag, dict):
            bag.pop(action_id, None)


def merge_action_parameters(
    current: Optional[list],
    values: Optional[Dict[str, str]] = None,
    increment: Optional[str] = None,
    only_if_absent: Optional[str] = None,
    remove: Optional[List[str]] = None,
) -> Optional[list]:
    """One action's parameters (plain ``{name, value, ...}`` dicts) with
    ``values`` set by name (replaced or appended), the counter ``increment``
    raised by one (a missing or unreadable count starts at 0) and the names in
    ``remove`` dropped. ``None`` when nothing changes, or when a parameter
    named ``only_if_absent`` already exists (a marker claimed once)."""
    params = [dict(p) for p in (current or []) if isinstance(p, dict)]
    names = {p.get("name") for p in params}
    if only_if_absent and only_if_absent in names:
        return None
    changes = dict(values or {})
    if increment:
        stored = next(
            (p.get("value") for p in params if p.get("name") == increment), None
        )
        try:
            count = int(stored or 0)
        except (TypeError, ValueError):
            count = 0
        changes[increment] = str(count + 1)
    dropped = set(remove or [])
    merged = [dict(p) for p in params if p.get("name") not in dropped]
    for name, value in changes.items():
        for p in merged:
            if p.get("name") == name:
                p["value"] = value
                break
        else:
            merged.append({"name": name, "value": value, "required": False})
    return None if merged == params else merged


CREDENTIALS_SECRET = "Credentials"


def replace_credential_secret(
    current: Optional[list], credential: str
) -> tuple:
    """One action's secrets (plain ``{name, value, ...}`` dicts) with the
    ``Credentials`` entry set to ``credential`` (appended when there was none;
    any other secret kept), and the ciphertext it replaced (``None`` when
    there was none)."""
    secrets = [dict(s) for s in (current or []) if isinstance(s, dict)]
    previous = None
    kept = []
    for secret in secrets:
        if secret.get("name") == CREDENTIALS_SECRET:
            previous = previous or secret.get("value") or None
            continue
        kept.append(secret)
    kept.append({"name": CREDENTIALS_SECRET, "value": credential, "required": False})
    return kept, previous


def replace_version_credentials(current: Optional[list], credential: str) -> Optional[list]:
    """A published version's copy of one action's secrets with every
    ``Credentials`` value set to ``credential``; ``None`` when it holds none
    (or only that one already)."""
    secrets = [dict(s) for s in (current or []) if isinstance(s, dict)]
    changed = False
    for secret in secrets:
        if secret.get("name") == CREDENTIALS_SECRET and secret.get("value") != credential:
            secret["value"] = credential
            changed = True
    return secrets if changed else None


# how long a PDF import's start waits for another start in the same workspace
# before it is refused as "an import is already running"
LOCK_WAIT_S = 10.0


class ImportLimitReached(Exception):
    """A workspace limit refused a new import (``code``: import_in_progress,
    daily_limit)."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def workspaces_with_stale_imports(records, stale_before) -> List[RecordId]:
    seen = []
    for record in records:
        if record.is_stale(stale_before) and record.workspace_id not in seen:
            seen.append(record.workspace_id)
    return seen


def lock_wait_s() -> float:
    """Read at call time, so tests can lengthen it on a loaded machine."""
    return LOCK_WAIT_S


def check_import_limits(
    active: int, today: int, max_active: int, max_per_day: int
) -> None:
    if active >= max_active:
        raise ImportLimitReached("import_in_progress")
    if today >= max_per_day:
        raise ImportLimitReached("daily_limit")


async def with_origin_titles(
    workspaces, templates: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """``templates`` (stored template documents) as the listings return them:
    ``id`` set, and ``imported_from`` (the id of the workspace a template was
    imported from) replaced by that workspace's title, or left out when the
    workspace no longer exists. The workspaces are read through
    ``workspaces`` (the identity group's repository): in 4.0 this was a
    ``$lookup`` into ``workspaces``, which both template repositories now
    compose instead (a join across groups finds nothing once the joined
    group leaves Mongo)."""
    origins = {
        t["imported_from"] for t in templates if t.get("imported_from") is not None
    }
    titles = {}
    if origins:
        for workspace in await workspaces.get_workspace_by_ids(list(origins)):
            titles[workspace.id] = workspace.title
    for template in templates:
        template["id"] = template["_id"]
        # $lookup + $unwind(preserveNull) + $set imported_from: "$workspace.title"
        origin = template.get("imported_from")
        if origin is not None and origin in titles:
            template["imported_from"] = titles[origin]
        else:
            template.pop("imported_from", None)
    return templates


_fn = getattr(func, SCHEMA)
TIMESTAMP_FIELDS = {"created_at", "updated_at", "published_at"}


# SQLSTATE lock_not_available: a lock wait ran past lock_timeout
LOCK_NOT_AVAILABLE = "55P03"


def _sqlstate(error: DBAPIError) -> Optional[str]:
    orig = getattr(error, "orig", None)
    return getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)


def _oid(value: Any) -> str:
    return str(value)


def _text(expr):
    return _fn.bc_text(expr)


def _bool(expr):
    return _fn.bc_bool(expr)


def _contains(expr, text: str):
    """``expr`` contains ``text``, ignoring case. The searched text is a
    literal: its ``%``, ``_`` and regex characters match themselves, so a
    search can neither fail on a bad pattern nor run an expensive one."""
    return expr.icontains(text, autoescape=True)


def _missing(container, key: str):
    """``{"path.key": {"$exists": False}}`` — also true when the container is null."""
    return func.coalesce(container.has_key(key), False).is_(False)


def _sort_terms(doc, sort: Optional[SortRequest], natural: Sequence[Any]):
    """``create_filter_pipeline(sort=...)``: one ``$sort`` on a document field.
    Mongo orders nulls/missing lowest, so ascending puts them first."""
    if not (sort and sort.sort_by):
        return list(natural)
    key = sort.sort_by
    expr = _fn.bc_ts(doc[key]) if key in TIMESTAMP_FIELDS else _text(doc[key])
    if sort.sort_order == SortOrder.ASCENDING:
        return [expr.asc().nulls_first(), *natural]
    return [expr.desc().nulls_last(), *natural]


def _fold(target: dict, source: dict, mapping: Dict[str, str]) -> None:
    """``$set: {target_key: "$source.key"}`` — a missing source path unsets."""
    for target_key, source_key in mapping.items():
        if source_key in source:
            target[target_key] = source[source_key]
        else:
            target.pop(target_key, None)


def _fold_settings(form: dict, workspace_form: dict) -> None:
    """``settings``: the workspace association's, plus the form's own declared
    language (``StandardFormSettings.language``), which only the form
    document keeps (the 4.0 Mongo pipeline's ``_SETTINGS_WITH_FORM_LANGUAGE``).
    When the association has no settings, the language alone."""
    own = form.get("settings")
    _fold(form, workspace_form, {"settings": "settings"})
    settings = form.get("settings")
    if not isinstance(own, dict) or "language" not in own:
        return
    if isinstance(settings, dict):
        form["settings"] = {**settings, "language": own["language"]}
    elif isinstance(own["language"], str):
        # no association settings: the language alone (a builder that
        # loaded none would clear it with its first save)
        form["settings"] = {"language": own["language"]}


class PostgresFormRepository(RecordRepository):
    row = FormRow
    document = FormDocument

    def __init__(self, session_factory, responder_groups, form_responses):
        super().__init__(session_factory)
        self._groups = responder_groups  # PostgresResponderGroupsRepository
        self._responses = form_responses  # PostgresFormResponseRepository

    # -- shared enrichment ----------------------------------------------------
    async def _attach_groups(self, forms: List[dict], workspace_id: RecordId) -> None:
        """The workspace's own groups only: a form held by several workspaces
        never carries another workspace's groups."""
        by_form = await self._groups.get_groups_by_form_ids(
            [form["form_id"] for form in forms], workspace_id
        )
        for form in forms:
            form["groups"] = by_form.get(form["form_id"], [])

    async def _attach_counts(
        self, forms: List[dict], workspace_id: RecordId
    ) -> None:
        """The workspace's own response and deletion-request counts (#768)."""
        ids = [form["form_id"] for form in forms]
        async with self._session() as session:
            links = (
                await session.execute(
                    select(WorkspaceFormRow.form_id, WorkspaceFormRow.workspace_id)
                    .where(WorkspaceFormRow.form_id.in_(ids))
                    .distinct()
                )
            ).all()
        owners: Dict[str, set] = {}
        for form_id, linked_workspace in links:
            owners.setdefault(form_id, set()).add(linked_workspace)
        scope = ResponseScope(
            workspace_id=RecordId(workspace_id),
            form_ids=tuple(ids),
            legacy_form_ids=tuple(
                f for f in ids if owners.get(f) == {_oid(workspace_id)}
            ),
        )
        responses = await self._responses.count_responses_with_answers_by_form_ids(
            scope
        )
        deletions = await self._responses.count_deletion_requests_by_form_ids(scope)
        for form in forms:
            form["responses"] = responses.get(form["form_id"], 0)
            form["deletion_requests"] = deletions.get(form["form_id"], 0)

    # -- drafts ---------------------------------------------------------------
    _published = exists(
        select(1).where(FormVersionRow.form_id == FormRow.form_id)
    ).correlate(FormRow)

    def _drafts_statement(self, workspace_id, form_id_list, sort):
        return (
            select(FormRow.doc, WorkspaceFormRow.doc, self._published)
            .join(
                WorkspaceFormRow,
                and_(
                    WorkspaceFormRow.form_id == FormRow.form_id,
                    WorkspaceFormRow.workspace_id == _oid(workspace_id),
                ),
            )
            .where(FormRow.form_id.in_(list(form_id_list)))
            .order_by(*_sort_terms(FormRow.doc, sort, (FormRow.created_at, FormRow.id)))
        )

    async def _drafts(
        self, rows: Iterable[Any], is_admin: bool, workspace_id: RecordId
    ) -> List[dict]:
        forms = []
        for form_doc, workspace_form_doc, published in rows:
            form = from_canonical_document(form_doc)
            workspace_form = from_canonical_document(workspace_form_doc)
            _fold_settings(form, workspace_form)
            _fold(form, workspace_form, {"imported_by": "user_id"})
            if is_admin:
                form["is_published"] = bool(published)
            forms.append(form)
        if forms:
            await self._attach_groups(forms, workspace_id)
            if is_admin:
                await self._attach_counts(forms, workspace_id)
        return forms

    async def get_forms_in_workspace(
        self,
        workspace_id: RecordId,
        form_id_list: List[str],
        is_admin: bool,
        sort=None,
    ) -> List[dict]:
        async with self._session() as session:
            rows = (
                await session.execute(
                    self._drafts_statement(workspace_id, form_id_list, sort)
                )
            ).all()
        return await self._drafts(rows, is_admin, workspace_id)

    async def paginate_forms_in_workspace(
        self,
        workspace_id: RecordId,
        form_id_list: List[str],
        is_admin: bool,
        sort=None,
    ) -> Page:
        async def transform(items):
            return await self._drafts(items, is_admin, workspace_id)

        async with self._session() as session:
            return await apaginate(
                session,
                self._drafts_statement(workspace_id, form_id_list, sort),
                transformer=transform,
                unique=False,
            )

    # -- published ------------------------------------------------------------
    def _latest_versions(self, form_id_list):
        """One row per form: its highest version (``$sort version:-1`` + ``$group``)."""
        return (
            select(FormVersionRow.form_id, FormVersionRow.doc)
            .distinct(FormVersionRow.form_id)
            .where(FormVersionRow.form_id.in_(list(form_id_list)))
            .order_by(FormVersionRow.form_id, FormVersionRow.version.desc())
            .subquery("latest")
        )

    def _published_statement(self, workspace_id, form_id_list, sort, get_actions):
        latest = self._latest_versions(form_id_list)
        stmt = select(latest.c.doc, WorkspaceFormRow.doc, FormRow.doc).join(
            WorkspaceFormRow,
            and_(
                WorkspaceFormRow.form_id == latest.c.form_id,
                WorkspaceFormRow.workspace_id == _oid(workspace_id),
            ),
        )
        if get_actions:  # $lookup forms + $unwind: drops versions without a draft
            stmt = stmt.join(FormRow, FormRow.form_id == latest.c.form_id)
        else:
            stmt = stmt.outerjoin(FormRow, FormRow.form_id == latest.c.form_id)
        natural = (_fn.bc_ts(latest.c.doc["created_at"]), latest.c.form_id)
        return stmt.order_by(*_sort_terms(latest.c.doc, sort, natural))

    async def _published_forms(
        self, rows: Iterable[Any], get_actions: bool, workspace_id: RecordId
    ):
        forms = []
        for version_doc, workspace_form_doc, form_doc in rows:
            form = from_canonical_document(version_doc)
            _fold_settings(form, from_canonical_document(workspace_form_doc))
            form["is_published"] = True
            if get_actions:
                draft = from_canonical_document(form_doc)
                _fold(
                    form,
                    draft,
                    {
                        "actions": "actions",
                        "parameters": "parameters",
                        "secrets": "secrets",
                    },
                )
            forms.append(form)
        if forms:
            await self._attach_counts(forms, workspace_id)
            if get_actions:
                await self._attach_groups(forms, workspace_id)
        return forms

    async def get_published_forms_in_workspace(
        self,
        workspace_id: RecordId,
        form_id_list: List[str],
        sort=None,
        get_actions=False,
    ) -> List[dict]:
        async with self._session() as session:
            rows = (
                await session.execute(
                    self._published_statement(
                        workspace_id, form_id_list, sort, get_actions
                    )
                )
            ).all()
        return await self._published_forms(rows, get_actions, workspace_id)

    async def paginate_published_forms_in_workspace(
        self,
        workspace_id: RecordId,
        form_id_list: List[str],
        sort=None,
        get_actions=False,
    ) -> Page:
        async def transform(items):
            return await self._published_forms(items, get_actions, workspace_id)

        async with self._session() as session:
            return await apaginate(
                session,
                self._published_statement(
                    workspace_id, form_id_list, sort, get_actions
                ),
                transformer=transform,
                unique=False,
            )

    # -- search ---------------------------------------------------------------
    async def search_form_in_workspace(
        self,
        workspace_id: RecordId,
        form_ids: List[str],
        query: str,
        published: bool = False,
    ):
        if published:
            matching = (
                select(FormVersionRow.form_id, FormVersionRow.doc)
                .distinct(FormVersionRow.form_id)
                .where(
                    FormVersionRow.form_id.in_(form_ids),
                    or_(
                        _contains(_text(FormVersionRow.doc["title"]), query),
                        _contains(_text(FormVersionRow.doc["description"]), query),
                    ),
                )
                .order_by(FormVersionRow.form_id, FormVersionRow.version.desc())
                .subquery("matching")
            )
            stmt = (
                select(matching.c.doc, WorkspaceFormRow.doc)
                .join(
                    WorkspaceFormRow,
                    and_(
                        WorkspaceFormRow.form_id == matching.c.form_id,
                        WorkspaceFormRow.workspace_id == _oid(workspace_id),
                    ),
                )
                .order_by(
                    _fn.bc_ts(matching.c.doc["created_at"]).desc(), matching.c.form_id
                )
            )
        else:
            stmt = (
                select(FormRow.doc, WorkspaceFormRow.doc, self._published)
                .join(
                    WorkspaceFormRow,
                    and_(
                        WorkspaceFormRow.form_id == FormRow.form_id,
                        WorkspaceFormRow.workspace_id == _oid(workspace_id),
                    ),
                )
                .where(
                    FormRow.form_id.in_(form_ids),
                    or_(
                        _contains(_text(FormRow.doc["title"]), query),
                        _contains(_text(FormRow.doc["description"]), query),
                    ),
                )
                .order_by(FormRow.created_at.desc(), FormRow.id)
            )
        async with self._session() as session:
            rows = (await session.execute(stmt)).all()
        forms = []
        for row in rows:
            form = from_canonical_document(row[0])
            _fold(
                form,
                from_canonical_document(row[1]),
                {"settings": "settings", "imported_by": "user_id"},
            )
            if not published:
                form["is_published"] = bool(row[2])
            forms.append(form)
        return forms

    # -- plain reads and writes ------------------------------------------------
    async def save_form(self, form: FormDocument):
        # As MongoDocument.save does: every save moves updated_at, which the
        # builder's conflict check (form_concurrency.py) relies on.
        form.updated_at = utcnow()
        return await self.upsert(form)

    async def save_form_version(
        self, form_version: FormVersionsDocument
    ) -> FormVersionsDocument:
        return await self.save_document(form_version, row=FormVersionRow)

    async def delete_versions_by_imported_form_id(self, imported_form_id: str):
        return await self.delete_where(
            FormVersionRow.imported_form_id == imported_form_id, row=FormVersionRow
        )

    async def get_forms_by_form_ids(self, form_ids: List[str]) -> List[FormDocument]:
        return await self.many(FormRow.form_id.in_(form_ids))

    async def delete_form(self, form_id: str):
        form = await self.one(FormRow.form_id == form_id)
        if not form:
            raise HTTPException(status_code=404, content="Form not found")
        return await self.delete_by_id(form.id)

    async def delete_forms(self, form_ids: List[str]):
        return await self.delete_where(FormRow.form_id.in_(form_ids))

    async def create_form(self, form: StandardForm) -> FormDocument:
        return await self.save_document(FormDocument(**form.model_dump(mode="json")))

    @staticmethod
    async def _locked_draft(session, form_id) -> Optional[FormDocument]:
        """The stored draft, its row locked for the rest of ``session``'s
        transaction; None when there is none. A write applies its change to
        this copy, never to one read earlier, so a concurrent write to other
        fields (an action removed, a credential replaced, a builder save) is
        kept, and a deleted draft stays deleted."""
        doc = (
            await session.execute(
                select(FormRow.doc)
                .where(FormRow.form_id == str(form_id))
                .order_by(FormRow.created_at, FormRow.id)
                .limit(1)
                .with_for_update()
            )
        ).scalar_one_or_none()
        return None if doc is None else decode(FormDocument, doc)

    async def update_form(self, form_id: RecordId, form: StandardForm):
        """A whole-form save onto the stored draft (``apply_form_update``),
        under its row lock; None when there is no draft."""
        async with self._session() as session, session.begin():
            stored = await self._locked_draft(session, form_id)
            if stored is None:
                return None
            apply_form_update(stored, form)
            stored.updated_at = utcnow()
            await session.execute(self._upsert_statement(row_values(stored)))
        return stored

    async def _stored_draft(self, form_id: RecordId):
        """The draft row's id, document and stored ``updated_at``."""
        async with self._session() as session:
            return (
                await session.execute(
                    select(FormRow.id, FormRow.doc, FormRow.updated_at)
                    .where(FormRow.form_id == _oid(form_id))
                    .order_by(FormRow.created_at, FormRow.id)
                    .limit(1)
                )
            ).one_or_none()

    async def update_form_if_unchanged(
        self,
        form_id: RecordId,
        form: StandardForm,
        expected_updated_at: datetime,
    ):
        """``update_form`` as a conditional write: refused with 409 when the
        stored draft is newer than ``expected_updated_at``
        (services/form_concurrency.py), including when another save lands
        between this read and this write: ``UPDATE ... WHERE id = :id AND
        updated_at = :stored``, the stored value being the one that passed
        the check."""
        found = await self._stored_draft(form_id)
        if found is None:
            return None
        form_document = decode(FormDocument, found.doc)
        ensure_not_changed_since(form_document.updated_at, expected_updated_at)
        apply_form_update(form_document, form)
        form_document.updated_at = next_updated_at(form_document.updated_at)
        values = row_values(form_document)
        unchanged = (
            FormRow.updated_at.is_(None)
            if found.updated_at is None
            else FormRow.updated_at == found.updated_at
        )
        async with self._session() as session, session.begin():
            result = await session.execute(
                update(FormRow)
                .where(FormRow.id == found.id, unchanged)
                .values(
                    {
                        FormRow.doc: values["doc"],
                        FormRow.updated_at: values["updated_at"],
                        FormRow.bc_source: values["bc_source"],
                        FormRow.bc_checksum: values["bc_checksum"],
                    }
                )
                .execution_options(synchronize_session=False)
            )
        if result.rowcount != 1:
            raise form_changed()
        return form_document

    async def set_form_logo(self, form_id: str, logo: Optional[str]):
        """Set (or, with None, clear) the draft's logo URL and nothing else,
        not ``updated_at`` either (4.0's ``$set``): under the row lock, on the
        stored copy. None when there is no draft (it is never re-inserted)."""
        async with self._session() as session, session.begin():
            stored = await self._locked_draft(session, form_id)
            if stored is None:
                return None
            stored.logo = logo
            await session.execute(self._upsert_statement(row_values(stored)))
        return stored

    async def get_form_document_by_id(self, form_id: str):
        return await self.one(FormRow.form_id == form_id)

    async def get_latest_version_of_form(self, form_id: RecordId):
        return await self.one_of(
            FormVersionRow,
            FormVersionsDocument,
            FormVersionRow.form_id == _oid(form_id),
            order_by=(FormVersionRow.version.desc(), FormVersionRow.id),
        )

    async def get_versions_of_form(self, form_id: RecordId):
        """Every published version of a form, oldest first."""
        return await self.many(
            FormVersionRow.form_id == _oid(form_id),
            order_by=(FormVersionRow.version, FormVersionRow.id),
            row=FormVersionRow,
            document=FormVersionsDocument,
        )

    async def get_form_by_by_version(
        self, form_id: RecordId, version: FormVersion | int
    ):
        if version == FormVersion.latest:
            return await self.get_latest_version_of_form(form_id=form_id)
        return await self.one_of(
            FormVersionRow,
            FormVersionsDocument,
            FormVersionRow.form_id == _oid(form_id),
            FormVersionRow.version == int(version),
        )

    async def publish_form(self, form: FormDocument, version: int):
        new_form_version = FormVersionsDocument(
            **form.model_dump(mode="json"), version=version
        )
        new_form_version.id = None
        return await self.save_document(new_form_version, row=FormVersionRow)

    async def get_form_by_id(self, form_id: RecordId):
        return await self.one(FormRow.form_id == _oid(form_id))

    async def remove_action_from_all_forms(self, action_id: RecordId):
        # Forms and published versions. Triggers hold {id, enabled}; ObjectIds
        # sit in the canonical doc as {"$oid": hex}, so @> finds them; rows
        # holding the action's parameters or secrets (OAuth runs before
        # attaching) match too. The rows stay locked while only this action is
        # removed, so a concurrent edit is neither lost nor overwritten.
        key = _oid(action_id)
        marker = [{"id": {"$oid": key}}]
        for row, document in (
            (FormRow, FormDocument),
            (FormVersionRow, FormVersionsDocument),
        ):
            actions = row.doc["actions"]
            matches = or_(
                *(actions[t.value].contains(marker) for t in Trigger),
                row.doc["parameters"].has_key(key),
                row.doc["secrets"].has_key(key),
            )
            async with self._session() as session, session.begin():
                docs = (
                    await session.execute(
                        select(row.doc).where(matches).with_for_update()
                    )
                ).scalars()
                for doc in docs.all():
                    stored = decode(document, doc)
                    detach_action(stored, key)
                    await session.execute(
                        self._upsert_statement(row_values(stored), row)
                    )

    async def update_action_parameters(
        self,
        form_id: str,
        action_id: str,
        values: Optional[Dict[str, str]] = None,
        increment: Optional[str] = None,
        only_if_absent: Optional[str] = None,
        remove: Optional[List[str]] = None,
    ) -> bool:
        """Change one action's parameters on the draft (``merge_action_parameters``)
        and nothing else: not ``updated_at`` (the builder's conflict check),
        not other actions. Under a row lock, so concurrent calls neither lose
        a count nor both claim a marker. True when it changed something."""
        key = str(action_id)
        async with self._session() as session, session.begin():
            doc = (
                await session.execute(
                    select(FormRow.doc)
                    .where(FormRow.form_id == str(form_id))
                    .order_by(FormRow.created_at, FormRow.id)
                    .limit(1)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if doc is None:
                return False
            stored = decode(FormDocument, doc)
            current = [
                parameter.model_dump(mode="json")
                for parameter in (stored.parameters or {}).get(key) or []
            ]
            merged = merge_action_parameters(
                current, values, increment, only_if_absent, remove
            )
            if merged is None:
                return False
            stored.parameters = {
                **(stored.parameters or {}),
                key: [ParameterValue(**parameter) for parameter in merged],
            }
            await session.execute(self._upsert_statement(row_values(stored)))
        return True

    async def replace_action_credential(
        self,
        form_id: str,
        action_id: str,
        credential: str,
        clear_parameters: Optional[List[str]] = None,
    ) -> dict:
        """Store a new credential for one action and drop the named parameters
        (the Sheets re-consent markers) on the draft (``updated_at`` and other
        actions untouched); every published version's copy of the action's
        credential is replaced too, so no stored copy of the old ciphertext is
        left. One transaction, under row locks. Returns ``{"stored": bool,
        "previous": str|None}``: the ciphertext the draft held before
        (``stored`` is False for an unknown form)."""
        key = str(action_id)
        async with self._session() as session, session.begin():
            doc = (
                await session.execute(
                    select(FormRow.doc)
                    .where(FormRow.form_id == str(form_id))
                    .order_by(FormRow.created_at, FormRow.id)
                    .limit(1)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if doc is None:
                return {"stored": False, "previous": None}
            stored = decode(FormDocument, doc)
            current = [
                secret.model_dump(mode="json")
                for secret in (stored.secrets or {}).get(key) or []
            ]
            secrets, previous = replace_credential_secret(current, credential)
            stored.secrets = {
                **(stored.secrets or {}),
                key: [ParameterValue(**secret) for secret in secrets],
            }
            params = [
                parameter.model_dump(mode="json")
                for parameter in (stored.parameters or {}).get(key) or []
            ]
            merged = merge_action_parameters(params, remove=clear_parameters)
            if merged is not None:
                stored.parameters = {
                    **(stored.parameters or {}),
                    key: [ParameterValue(**parameter) for parameter in merged],
                }
            await session.execute(self._upsert_statement(row_values(stored)))
            versions = (
                await session.execute(
                    select(FormVersionRow.doc)
                    .where(
                        FormVersionRow.form_id == str(form_id),
                        FormVersionRow.doc["secrets"].has_key(key),
                    )
                    .with_for_update()
                )
            ).scalars()
            for version_doc in versions.all():
                version = decode(FormVersionsDocument, version_doc)
                replaced = replace_version_credentials(
                    [
                        secret.model_dump(mode="json")
                        for secret in (version.secrets or {}).get(key) or []
                    ],
                    credential,
                )
                if replaced is None:
                    continue
                version.secrets = {
                    **(version.secrets or {}),
                    key: [ParameterValue(**secret) for secret in replaced],
                }
                await session.execute(
                    self._upsert_statement(row_values(version), FormVersionRow)
                )
        return {"stored": True, "previous": previous}

    async def get_forms_with_action_secrets(
        self, action_ids: List[str]
    ) -> List[FormDocument]:
        if not action_ids:
            return []
        return await self.many(
            or_(*(FormRow.doc["secrets"].has_key(str(key)) for key in action_ids))
        )

    async def update_form_actions(
        self,
        form_id: RecordId,
        action_id: RecordId,
        form: StandardForm,
        payload: FormActionsDto,
    ):
        """Set one secret (by name) of one action on the stored draft, under
        its row lock (``form`` is the caller's earlier read: only its id is
        used, so nothing else of it is written back). Moves ``updated_at``,
        as the 4.0 save did. None when there is no draft; the stored draft,
        unchanged and not written, when the action has no secrets on it (any
        more)."""
        key = str(action_id)
        async with self._session() as session, session.begin():
            stored = await self._locked_draft(session, form_id)
            if stored is None:
                return None
            if key not in (stored.secrets or {}):
                # the action was removed meanwhile: nothing to set
                return stored
            secrets = stored.secrets[key] or []
            for secret in secrets:
                if secret.name == payload.name:
                    secret.value = payload.value
            stored.secrets = {**(stored.secrets or {}), key: secrets}
            stored.touch()
            await session.execute(self._upsert_statement(row_values(stored)))
        return stored


class PostgresWorkspaceFormRepository(RecordRepository):
    row = WorkspaceFormRow
    document = WorkspaceFormDocument

    def __init__(self, session_factory, responder_groups):
        super().__init__(session_factory)
        self._groups = responder_groups  # PostgresResponderGroupsRepository

    async def find_workspace_form(
        self, workspace_id: RecordId, form_id: str
    ) -> Optional[WorkspaceFormDocument]:
        return await self.one(
            WorkspaceFormRow.form_id == form_id,
            WorkspaceFormRow.workspace_id == _oid(workspace_id),
        )

    async def list_in_workspace(
        self, workspace_id: RecordId
    ) -> List[WorkspaceFormDocument]:
        return await self.many(WorkspaceFormRow.workspace_id == _oid(workspace_id))

    async def save(
        self, workspace_form: WorkspaceFormDocument
    ) -> WorkspaceFormDocument:
        return await self.save_document(workspace_form)

    async def _locked_link(self, session, *where) -> Optional[WorkspaceFormDocument]:
        """The stored link, its row locked for the rest of ``session``'s
        transaction; None when there is none."""
        doc = (
            await session.execute(
                select(WorkspaceFormRow.doc)
                .where(*where)
                .order_by(WorkspaceFormRow.created_at, WorkspaceFormRow.id)
                .limit(1)
                .with_for_update()
            )
        ).scalar_one_or_none()
        return None if doc is None else decode(WorkspaceFormDocument, doc)

    async def update(
        self, item_id: str, item: WorkspaceFormDocument
    ) -> WorkspaceFormDocument:
        """Store ``item``'s settings and update status on the stored link,
        under its row lock (what the callers change; the rest of the link is
        never written back from their earlier read). 404 when it is gone."""
        async with self._session() as session, session.begin():
            stored = await self._locked_link(session, WorkspaceFormRow.id == _oid(item_id))
            if stored is None:
                raise HTTPException(HTTPStatus.NOT_FOUND, "Form not found in ")
            stored.settings = item.settings
            stored.last_update_status = item.last_update_status
            stored.touch()
            await session.execute(self._upsert_statement(row_values(stored)))
        return stored

    async def save_workspace_form(
        self,
        workspace_id: RecordId,
        form_id: str,
        user_id: str,
        workspace_form_settings: WorkspaceFormSettings,
    ) -> WorkspaceFormDocument:
        # an existing link of this user: its settings, under its row lock
        async with self._session() as session, session.begin():
            stored = await self._locked_link(
                session,
                WorkspaceFormRow.workspace_id == _oid(workspace_id),
                WorkspaceFormRow.form_id == form_id,
                WorkspaceFormRow.user_id == user_id,
            )
            if stored is not None:
                stored.settings = workspace_form_settings
                stored.touch()
                await session.execute(self._upsert_statement(row_values(stored)))
        if stored is not None:
            return stored
        workspace_form = WorkspaceFormDocument(
            workspace_id=workspace_id,
            form_id=form_id,
            user_id=user_id,
            settings=workspace_form_settings,
        )
        try:
            return await self.save_document(workspace_form)
        except IntegrityError:  # uq_workspace_forms_workspace_form: linked meanwhile
            existing = await self.find_workspace_form(workspace_id, form_id)
            if existing is None:
                raise
            return existing

    @staticmethod
    def _settings():
        return WorkspaceFormRow.doc["settings"]

    @classmethod
    def _slug_match(cls, value: str):
        return or_(
            WorkspaceFormRow.form_id == value, WorkspaceFormRow.custom_url == value
        )

    @classmethod
    def _not_hidden(cls):
        return or_(
            WorkspaceFormRow.hidden.is_(False), _missing(cls._settings(), "hidden")
        )

    async def get_workspace_form_in_workspace(
        self, workspace_id: RecordId, query: str, is_admin=True
    ):
        where = [
            WorkspaceFormRow.workspace_id == _oid(workspace_id),
            self._slug_match(query),
        ]
        if not is_admin:
            where.append(WorkspaceFormRow.private.is_(False))
        try:
            return await self.one(*where)
        except SQLAlchemyError:
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                content=MESSAGE_DATABASE_EXCEPTION,
            )

    async def get_workspace_forms_in_workspace(
        self,
        workspace_id: RecordId,
        is_not_admin: bool = False,
        user: User = None,
        form_id: Optional[str] = None,
        form_id_or_slug: Optional[str] = None,
        pinned_only: bool = False,
        id_only: bool = False,
        filter_closed=False,
    ) -> List[Dict[str, Any]]:
        settings = self._settings()
        where = [WorkspaceFormRow.workspace_id == _oid(workspace_id)]
        if form_id is not None:
            where.append(WorkspaceFormRow.form_id == form_id)
        if form_id_or_slug is not None:
            where.append(self._slug_match(form_id_or_slug))
        if pinned_only:
            where.append(WorkspaceFormRow.pinned.is_(True))
        if not is_not_admin and user:
            where.append(or_(self._not_hidden(), WorkspaceFormRow.user_id == user.id))
        if is_not_admin and not user:
            where.extend([self._not_hidden(), WorkspaceFormRow.private.is_(False)])
        if filter_closed:
            close_date = settings["form_close_date"]
            where.append(
                or_(
                    _missing(settings, "form_close_date"),
                    func.jsonb_typeof(close_date) == "null",
                    _text(close_date) == "",
                    _text(close_date) >= datetime.now(timezone.utc).isoformat(),
                )
            )
        if is_not_admin and user:
            where.append(self._not_hidden())
        try:
            async with self._session() as session:
                docs = (
                    (
                        await session.execute(
                            select(WorkspaceFormRow.doc)
                            .where(*where)
                            .order_by(*self._order())
                        )
                    )
                    .scalars()
                    .all()
                )
        except SQLAlchemyError:
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                content=MESSAGE_DATABASE_EXCEPTION,
            )
        workspace_forms = [from_canonical_document(doc) for doc in docs]
        if is_not_admin and user:
            # private forms stay visible to responders this workspace's own
            # groups admit (a member, or a regex match); another workspace's
            # groups on the same form count for nothing here
            admitted = await self._groups.get_form_ids_accessible_to(
                [wf["form_id"] for wf in workspace_forms], user.sub, workspace_id
            )
            workspace_forms = [
                wf
                for wf in workspace_forms
                if (wf.get("settings") or {}).get("private") is False
                or wf["form_id"] in admitted
            ]
        if id_only:
            return [{"form_id": wf["form_id"]} for wf in workspace_forms]
        return workspace_forms

    async def get_form_ids_in_workspace(
        self,
        workspace_id: RecordId,
        is_not_admin: bool = False,
        user: User = None,
        pinned_only: bool = False,
        form_id: Optional[str] = None,
        form_id_or_slug: Optional[str] = None,
        filter_closed: bool = False,
    ):
        workspace_forms = await self.get_workspace_forms_in_workspace(
            workspace_id=workspace_id,
            is_not_admin=is_not_admin,
            user=user,
            form_id=form_id,
            form_id_or_slug=form_id_or_slug,
            pinned_only=pinned_only,
            id_only=True,
            filter_closed=filter_closed,
        )
        return list(set([a["form_id"] for a in workspace_forms]))

    async def get_workspace_form_with_custom_slug_form_id(
        self, workspace_id: RecordId, custom_url: str
    ):
        return await self.one(
            WorkspaceFormRow.workspace_id == _oid(workspace_id),
            self._slug_match(custom_url),
        )

    async def get_workspace_ids_for_form_id(self, form_id):
        return [
            workspace_form.workspace_id
            for workspace_form in await self.many(WorkspaceFormRow.form_id == form_id)
        ]

    async def delete_form_in_workspace(
        self, workspace_id: RecordId, form_id: str
    ):
        workspace_form = await self.find_workspace_form(workspace_id, form_id)
        if not workspace_form:
            raise HTTPException(status_code=404, content="Form not found in Workspace")
        await self.delete_by_id(workspace_form.id)
        return workspace_form

    async def check_is_form_imported_in_other_workspace(
        self, workspace_id: RecordId, form_id: str
    ):
        for workspace_form in await self.many(WorkspaceFormRow.form_id == form_id):
            if workspace_form.workspace_id != workspace_id:
                raise HTTPException(
                    status_code=HTTPStatus.CONFLICT,
                    content="Form has already been imported to another workspace",
                )

    async def get_form_ids_imported_by_user(
        self, workspace_id: RecordId, user_id: str
    ):
        forms = await self.many(
            WorkspaceFormRow.workspace_id == _oid(workspace_id),
            WorkspaceFormRow.user_id == user_id,
        )
        return [form.form_id for form in forms]

    async def get_form_ids_in_workspaces_and_imported_by_user(
        self, workspace_ids: List[RecordId], user: User
    ):
        forms = await self.many(
            or_(
                WorkspaceFormRow.workspace_id.in_([_oid(i) for i in workspace_ids]),
                WorkspaceFormRow.user_id == user.id,
            ),
            _text(self._settings()["provider"]).is_distinct_from("self"),
        )
        return [form.form_id for form in forms]

    async def count_forms_of_account(
        self, workspace_ids: List[RecordId], user_id: str
    ) -> int:
        forms = await self.many(
            or_(
                WorkspaceFormRow.workspace_id.in_([_oid(i) for i in workspace_ids]),
                WorkspaceFormRow.user_id == user_id,
            )
        )
        return len({form.form_id for form in forms})

    async def links_by_form(self) -> Dict[str, List[str]]:
        """``{form_id: [workspace ids]}`` of every link, in insertion order
        (the import check of ``backend.db.forms_import``)."""
        links: Dict[str, List[str]] = {}
        async with self._session() as session:
            rows = await session.execute(
                select(WorkspaceFormRow.form_id, WorkspaceFormRow.workspace_id).order_by(
                    WorkspaceFormRow.created_at, WorkspaceFormRow.id
                )
            )
            for form_id, workspace in rows:
                if not workspace:
                    continue
                workspaces = links.setdefault(str(form_id), [])
                if workspace not in workspaces:
                    workspaces.append(workspace)
        return links

    async def delete_forms(self, form_ids):
        return await self.delete_where(WorkspaceFormRow.form_id.in_(list(form_ids)))

    async def get_workspace_forms_form_ids(self, form_ids: List[str]):
        return await self.many(WorkspaceFormRow.form_id.in_(form_ids))

    async def check_if_form_exists_in_workspace(
        self, workspace_id: RecordId, form_id: str
    ):
        workspace_form = await self.find_workspace_form(workspace_id, form_id)
        return True if workspace_form is not None else False

    # -- platform metrics (admin dashboard); forms are dated by ObjectId ---------
    @staticmethod
    def _created_since(created_since: Optional[datetime]) -> list:
        if created_since is None:
            return []
        return [WorkspaceFormRow.id >= str(object_id_at(created_since))]

    async def count_workspace_forms(
        self, created_since: Optional[datetime] = None
    ) -> int:
        return await self.count(*self._created_since(created_since))

    async def count_published_workspace_forms(self) -> int:
        return await self.count(
            exists().where(FormVersionRow.form_id == WorkspaceFormRow.form_id)
        )

    async def count_workspace_forms_by_provider(self) -> Dict[Optional[str], int]:
        provider = _text(self._settings()["provider"])
        async with self._session() as session:
            rows = (
                await session.execute(
                    select(provider, func.count())
                    .select_from(WorkspaceFormRow)
                    .group_by(provider)
                )
            ).all()
        return {name: n for name, n in rows}

    async def count_form_creators(
        self, created_since: Optional[datetime] = None
    ) -> int:
        async with self._session() as session:
            return (
                await session.execute(
                    select(func.count(WorkspaceFormRow.user_id.distinct())).where(
                        WorkspaceFormRow.user_id.is_not(None),
                        WorkspaceFormRow.user_id != "",
                        *self._created_since(created_since),
                    )
                )
            ).scalar_one()

    async def count_workspace_forms_created_per_period(
        self, boundaries: List[datetime]
    ) -> List[int]:
        return await postgres_counts_per_period(
            self, WorkspaceFormRow.id, [str(object_id_at(b)) for b in boundaries]
        )


class PostgresWorkspaceConsentRepo(RecordRepository):
    row = WorkspaceConsentRow
    document = WorkspaceConsentDocument

    async def get_workspace_consents(self, workspace_id: RecordId):
        return await self.many(WorkspaceConsentRow.workspace_id == _oid(workspace_id))

    async def create_workspace_consent(
        self, workspace_id: RecordId, consent: ConsentCamelModel
    ):
        consent_document = WorkspaceConsentDocument(**consent.model_dump(mode="json"))
        consent_document.workspace_id = workspace_id
        return await self.save_document(consent_document)


class PostgresFormTemplateRepository(RecordRepository):
    row = FormTemplateRow
    document = FormTemplateDocument

    def __init__(self, session_factory, workspaces):
        super().__init__(session_factory)
        self._workspaces = workspaces  # the identity group's workspace repository

    async def get_templates_with_creator(
        self,
        v2: Optional[bool] = None,
        workspace_id: RecordId = None,
        template_id: RecordId = None,
        predefined_workspace: bool = False,
    ):
        builder_version = _text(FormTemplateRow.doc["builder_version"])
        where = [
            (
                FormTemplateRow.workspace_id == _oid(workspace_id)
                if workspace_id is not None
                else FormTemplateRow.workspace_id.is_(None)
            ),
            builder_version == "v2" if v2 else builder_version.is_distinct_from("v2"),
        ]
        if predefined_workspace:
            where.append(_bool(FormTemplateRow.doc["settings"]["is_public"]).is_(True))
        if template_id:
            where.append(FormTemplateRow.id == _oid(template_id))
        async with self._session() as session:
            docs = (
                (
                    await session.execute(
                        select(FormTemplateRow.doc)
                        .where(*where)
                        .order_by(FormTemplateRow.created_at.desc(), FormTemplateRow.id)
                    )
                )
                .scalars()
                .all()
            )
        return await with_origin_titles(
            self._workspaces, [from_canonical_document(doc) for doc in docs]
        )

    async def get_template_by_id(self, template_id: RecordId):
        return await self.one(FormTemplateRow.id == _oid(template_id))

    async def get_v2_template_by_title(
        self, title: str
    ) -> Optional[FormTemplateDocument]:
        return await self.one(
            _text(FormTemplateRow.doc["title"]) == title,
            _text(FormTemplateRow.doc["builder_version"]) == "v2",
        )

    async def get_template_by_workspace_id_n_template_id(
        self, workspace_id: RecordId, template_id: RecordId
    ):
        return await self.one(
            FormTemplateRow.id == _oid(template_id),
            FormTemplateRow.workspace_id == _oid(workspace_id),
        )

    async def get_template_by_id_with_creator(
        self, workspace_id: RecordId, template_id: RecordId
    ):
        templates = await self.get_templates_with_creator(
            workspace_id=workspace_id, template_id=template_id
        )
        if len(templates) > 0:
            return templates[0]
        raise HTTPException(HTTPStatus.NOT_FOUND, content=MESSAGE_NOT_FOUND)

    async def import_template_to_workspace(
        self, workspace_id: RecordId, template_id: RecordId
    ):
        template = await self.get_template_by_id(template_id)
        imported_template = FormTemplateDocument(**template.model_dump(mode="json"))
        imported_template.id = None
        imported_template.imported_from = template.workspace_id
        imported_template.workspace_id = workspace_id
        imported_template.settings = StandardTemplateSetting()
        return await self.save_document(imported_template)

    async def create_new_template(
        self,
        workspace_id: RecordId,
        template_body: StandardFormTemplate,
        user: User,
    ):
        template = FormTemplateDocument(**template_body.model_dump(mode="json"))
        template.workspace_id = workspace_id
        template.created_by = user.id
        return await self.save_document(template)

    async def update_template(
        self, template_id: RecordId, template_body: StandardFormTemplate
    ):
        """The template's content from ``template_body``, applied to the
        stored template under its row lock; None when it is gone."""
        async with self._session() as session, session.begin():
            doc = (
                await session.execute(
                    select(FormTemplateRow.doc)
                    .where(FormTemplateRow.id == _oid(template_id))
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if doc is None:
                return None
            template = decode(FormTemplateDocument, doc)
            template.fields = template_body.fields
            # Only the settings the body names change: one it leaves out
            # (public, language, retention) stays as stored; an explicit null
            # clears it.
            if template_body.settings is not None:
                merged = template.settings or StandardTemplateSetting()
                for name in template_body.settings.model_fields_set:
                    setattr(merged, name, getattr(template_body.settings, name))
                template.settings = merged
            template.title = template_body.title
            template.description = template_body.description
            template.button_text = template_body.button_text
            template.logo = template_body.logo
            template.cover_image = template_body.cover_image
            template.touch()
            await session.execute(
                self._upsert_statement(row_values(template), FormTemplateRow)
            )
        return template

    async def save(self, template: FormTemplateDocument) -> FormTemplateDocument:
        return await self.save_document(template)

    async def delete_template(self, template_id: RecordId):
        template = await self.get_template_by_id(template_id)
        if not template:
            raise HTTPException(HTTPStatus.NOT_FOUND, "Template not found")
        await self.delete_by_id(template.id)
        return str(template_id)


class PostgresMediaLibraryRepository(RecordRepository):
    row = MediaLibraryRow
    document = MediaLibraryDocument

    async def get_media_library_by_worksapce_id(
        self, workspace_id: str, media_query: str
    ):
        where = [MediaLibraryRow.workspace_id == workspace_id]
        if media_query is not None:
            where.append(_contains(MediaLibraryRow.media_name, media_query))
        return await self.many(
            *where, order_by=(MediaLibraryRow.created_at.desc(), MediaLibraryRow.id)
        )

    async def get_single_media_from_workspace_library(
        self, workspace_id: str, media_id: RecordId
    ):
        return await self.one(
            MediaLibraryRow.workspace_id == workspace_id,
            MediaLibraryRow.media_id == _oid(media_id),
        )

    async def add_media_in_workspace_library(
        self,
        workspace_id: str,
        media_url: str,
        media_type: str,
        media_name: str,
        s3_key: str,
    ):
        media = MediaLibraryDocument(
            media_id=RecordId(),
            workspace_id=workspace_id,
            media_type=media_type,
            media_name=media_name,
            media_url=media_url,
            s3_key=s3_key,
        )
        return await self.save_document(media)

    async def delete_media_from_library(
        self, workspace_id: str, media_id: RecordId
    ):
        media = await self.get_single_media_from_workspace_library(
            workspace_id, media_id
        )
        await self.delete_by_id(
            media.id
        )  # AttributeError when missing, as in 4.0
        return media_id


def _import_kind(kind: Optional[str]):
    """Rows of one kind of import: ``"pdf"`` (a record written before
    ``source_kind`` existed has none) or another kind by name; None for all."""
    if kind is None:
        return true()
    value = _text(FormImportRow.doc["source_kind"])
    if kind == "pdf":
        return or_(value.is_(None), value == "pdf")
    return value == kind


def _failed_attempt():
    """A refused attempt of the Open Formulieren import: failed, no form."""
    return and_(
        FormImportRow.status == ImportStatus.FAILED,
        FormImportRow.form_id.is_(None),
    )


class PostgresFormImportRepository(RecordRepository):
    row = FormImportRow
    document = FormImportDocument

    async def save(self, document: FormImportDocument) -> FormImportDocument:
        return await self.save_document(document)

    async def create_within_limits(
        self,
        document: FormImportDocument,
        max_active: int,
        max_per_day: int,
        since: datetime,
    ) -> FormImportDocument:
        """Store a new import unless a workspace limit refuses it
        (``ImportLimitReached``): a transaction-scoped advisory lock per
        workspace serialises starts, then the counts and the insert run in the
        same transaction. A start that waits longer than ``LOCK_WAIT_S`` is
        refused as busy (not the session's lock_timeout error)."""
        self._check_collection(document, FormImportRow)
        workspace_id = _oid(document.workspace_id)
        async with self._session() as session, session.begin():
            await self._lock_workspace(session, workspace_id)
            active, today = await self._limit_counts(session, workspace_id, since)
            check_import_limits(active, today, max_active, max_per_day)
            await session.execute(self._upsert_statement(row_values(document)))
        return document

    @staticmethod
    async def _lock_workspace(session, workspace_id: str) -> None:
        """The workspace's advisory lock for the rest of the transaction; a
        start that waits longer than ``LOCK_WAIT_S`` is refused as busy."""
        wait_ms = max(1, int(lock_wait_s() * 1000))
        await session.execute(text(f"SET LOCAL lock_timeout = '{wait_ms}ms'"))
        try:
            await session.execute(
                select(
                    func.pg_advisory_xact_lock(
                        func.hashtextextended(f"form_imports:{workspace_id}", 0)
                    )
                )
            )
        except DBAPIError as error:
            if _sqlstate(error) == LOCK_NOT_AVAILABLE:
                raise ImportLimitReached("import_in_progress") from None
            raise

    async def touch(self, import_id: RecordId, at: datetime) -> bool:
        """Move an active import's heartbeat: the row is locked while only its
        heartbeat changes, so a concurrent pipeline save is never undone."""
        async with self._session() as session, session.begin():
            doc = (
                await session.execute(
                    select(FormImportRow.doc)
                    .where(
                        FormImportRow.id == _oid(import_id),
                        FormImportRow.status.in_(list(ImportStatus.ACTIVE)),
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if doc is None:
                return False
            stored = decode(FormImportDocument, doc)
            stored.heartbeat_at = at
            await session.execute(self._upsert_statement(row_values(stored)))
        return True

    async def expire_stale(
        self, workspace_id: RecordId, stale_before: datetime, now: datetime
    ) -> List[FormImportDocument]:
        """Under the workspace's advisory lock, the
        active rows are locked, and those without progress since
        ``stale_before`` are marked failed (``interrupted``)."""
        expired = []
        workspace = _oid(workspace_id)
        async with self._session() as session, session.begin():
            await self._lock_workspace(session, workspace)
            docs = (
                (
                    await session.execute(
                        select(FormImportRow.doc)
                        .where(
                            FormImportRow.workspace_id == workspace,
                            FormImportRow.status.in_(list(ImportStatus.ACTIVE)),
                        )
                        .with_for_update()
                    )
                )
                .scalars()
                .all()
            )
            for doc in docs:
                record = decode(FormImportDocument, doc)
                if not record.is_stale(stale_before):
                    continue
                record.mark_interrupted(now)
                await session.execute(self._upsert_statement(row_values(record)))
                expired.append(record)
        return expired

    async def stale_workspaces(self, stale_before: datetime) -> List[RecordId]:
        active = await self.many(FormImportRow.status.in_(list(ImportStatus.ACTIVE)))
        return workspaces_with_stale_imports(active, stale_before)

    async def _limit_counts(self, session, workspace_id: str, since: datetime):
        # the PDF import's limits count PDF imports only
        """(running imports, imports created since ``since``), read in the
        transaction that holds the workspace's advisory lock."""
        active = (
            await session.execute(
                select(func.count())
                .select_from(FormImportRow)
                .where(
                    FormImportRow.workspace_id == workspace_id,
                    FormImportRow.status.in_(list(ImportStatus.ACTIVE)),
                    _import_kind("pdf"),
                )
            )
        ).scalar_one()
        today = (
            await session.execute(
                select(func.count())
                .select_from(FormImportRow)
                .where(
                    FormImportRow.workspace_id == workspace_id,
                    FormImportRow.created_at >= since,
                    _import_kind("pdf"),
                )
            )
        ).scalar_one()
        return active, today

    async def get(self, import_id: RecordId) -> Optional[FormImportDocument]:
        return await self.one(FormImportRow.id == _oid(import_id))

    async def list_by_workspace(
        self,
        workspace_id: RecordId,
        limit: int = 20,
        kind: Optional[str] = "pdf",
        include_failed: bool = False,
    ) -> List[FormImportDocument]:
        """The workspace's imports of one kind, newest first. Refused attempts
        of the Open Formulieren import (failed, no form: kept only to be
        counted) are left out unless ``include_failed``."""
        return await self.many(
            FormImportRow.workspace_id == _oid(workspace_id),
            _import_kind(kind),
            true()
            if include_failed or kind != "open_formulieren"
            else not_(_failed_attempt()),
            order_by=(FormImportRow.created_at.desc(), FormImportRow.id.desc()),
            limit=limit,
        )

    async def count_created_since(
        self,
        workspace_id: RecordId,
        since: datetime,
        kind: Optional[str] = "pdf",
        status: Optional[str] = None,
    ) -> int:
        return await self.count(
            FormImportRow.workspace_id == _oid(workspace_id),
            FormImportRow.created_at >= since,
            _import_kind(kind),
            FormImportRow.status == status if status else true(),
        )

    async def count_active(self, workspace_id: RecordId) -> int:
        return await self.count(
            FormImportRow.workspace_id == _oid(workspace_id),
            FormImportRow.status.in_(list(ImportStatus.ACTIVE)),
            _import_kind("pdf"),
        )

    async def delete_failed_attempts_before(
        self, before: datetime, kind: str = "open_formulieren"
    ) -> int:
        """Delete the refused attempts of an import ``kind`` made before
        ``before`` (failed, no form: a note kept only for the daily count)."""
        return await self.delete_where(
            _import_kind(kind), _failed_attempt(), FormImportRow.created_at < before
        )

    async def delete_by_form_ids(self, form_ids: List[str]) -> int:
        return await self.delete_where(FormImportRow.form_id.in_(list(form_ids)))
