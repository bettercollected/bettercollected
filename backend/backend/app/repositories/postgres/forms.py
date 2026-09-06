"""Postgres twins of the forms-group repositories.

The Mongo originals build aggregation pipelines whose ``$lookup``s fall into
two kinds, handled differently here (plans/postgres-consolidation.md §4):

* **within the group** — forms ⋈ workspace_forms ⋈ form_versions — become SQL
  joins on the spine columns;
* **into another group** — responder groups, response and deletion-request
  counts (``responses``), the workspace a template was imported from
  (``identity``) — are *composed*: the twin reads its own tables, then asks the
  other group's *routed* repository in one batched call, so the answer comes
  from whichever store currently serves that group.

Results keep the raw-document shape of the aggregations (``FormDtoCamelModel``
and friends consume dicts), rebuilt from the row's canonical ``doc``.
"""

from datetime import datetime, timezone
from http import HTTPStatus
from typing import Any, Dict, Iterable, List, Optional, Sequence

from beanie import PydanticObjectId
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import apaginate
from sqlalchemy import and_, exists, func, not_, or_, select
from sqlalchemy.exc import SQLAlchemyError

from backend.app.exceptions import HTTPException
from backend.app.models.dtos.consent import ConsentCamelModel
from backend.app.models.dtos.form_actions_dto import FormActionsDto
from backend.app.models.enum.FormVersion import FormVersion
from backend.app.models.filter_queries.sort import SortOrder, SortRequest
from backend.app.models.template import StandardFormTemplate, StandardTemplateSetting
from backend.app.models.workspace import WorkspaceFormSettings
from backend.app.schemas.consent import WorkspaceConsentDocument
from backend.app.schemas.form_versions import FormVersionsDocument
from backend.app.schemas.media_library import MediaLibraryDocument
from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.template import FormTemplateDocument
from backend.app.schemas.workspace_form import WorkspaceFormDocument
from backend.db.base import SCHEMA
from backend.db.models import (
    FormRow,
    FormTemplateRow,
    FormVersionRow,
    MediaLibraryRow,
    WorkspaceConsentRow,
    WorkspaceFormRow,
)
from common.constants import MESSAGE_DATABASE_EXCEPTION, MESSAGE_NOT_FOUND
from common.db import PostgresRepositoryBase, from_canonical_document
from common.models.standard_form import StandardForm
from common.models.user import User

_fn = getattr(func, SCHEMA)
TIMESTAMP_FIELDS = {"created_at", "updated_at", "published_at"}


def _oid(value: Any) -> str:
    return str(value)


def _text(expr):
    return _fn.bc_text(expr)


def _bool(expr):
    return _fn.bc_bool(expr)


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


class PostgresFormRepository(PostgresRepositoryBase):
    row = FormRow
    document = FormDocument

    def __init__(self, session_factory, responder_groups, form_responses):
        super().__init__(session_factory)
        self._groups = responder_groups  # routed ResponderGroupsRepository
        self._responses = form_responses  # routed FormResponseRepository

    # -- shared enrichment ----------------------------------------------------
    async def _attach_groups(self, forms: List[dict]) -> None:
        by_form = await self._groups.get_groups_by_form_ids(
            [form["form_id"] for form in forms]
        )
        for form in forms:
            form["groups"] = by_form.get(form["form_id"], [])

    async def _attach_counts(self, forms: List[dict]) -> None:
        ids = [form["form_id"] for form in forms]
        responses = await self._responses.count_responses_with_answers_by_form_ids(ids)
        deletions = await self._responses.count_deletion_requests_by_form_ids(ids)
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

    async def _drafts(self, rows: Iterable[Any], is_admin: bool) -> List[dict]:
        forms = []
        for form_doc, workspace_form_doc, published in rows:
            form = from_canonical_document(form_doc)
            workspace_form = from_canonical_document(workspace_form_doc)
            _fold(
                form, workspace_form, {"settings": "settings", "imported_by": "user_id"}
            )
            if is_admin:
                form["is_published"] = bool(published)
            forms.append(form)
        if forms:
            await self._attach_groups(forms)
            if is_admin:
                await self._attach_counts(forms)
        return forms

    async def get_forms_in_workspace(
        self,
        workspace_id: PydanticObjectId,
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
        return await self._drafts(rows, is_admin)

    async def paginate_forms_in_workspace(
        self,
        workspace_id: PydanticObjectId,
        form_id_list: List[str],
        is_admin: bool,
        sort=None,
    ) -> Page:
        async def transform(items):
            return await self._drafts(items, is_admin)

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

    async def _published_forms(self, rows: Iterable[Any], get_actions: bool):
        forms = []
        for version_doc, workspace_form_doc, form_doc in rows:
            form = from_canonical_document(version_doc)
            _fold(
                form,
                from_canonical_document(workspace_form_doc),
                {"settings": "settings"},
            )
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
            await self._attach_counts(forms)
            if get_actions:
                await self._attach_groups(forms)
        return forms

    async def get_published_forms_in_workspace(
        self,
        workspace_id: PydanticObjectId,
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
        return await self._published_forms(rows, get_actions)

    async def paginate_published_forms_in_workspace(
        self,
        workspace_id: PydanticObjectId,
        form_id_list: List[str],
        sort=None,
        get_actions=False,
    ) -> Page:
        async def transform(items):
            return await self._published_forms(items, get_actions)

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
        workspace_id: PydanticObjectId,
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
                        _text(FormVersionRow.doc["title"]).op("~*")(query),
                        _text(FormVersionRow.doc["description"]).op("~*")(query),
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
                        _text(FormRow.doc["title"]).op("~*")(query),
                        _text(FormRow.doc["description"]).op("~*")(query),
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
        return await self.upsert(form)

    async def save_form_version(
        self, form_version: FormVersionsDocument
    ) -> FormVersionsDocument:
        return await self.upsert(form_version, row=FormVersionRow)

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
        return await self.upsert(FormDocument(**form.model_dump(mode="json")))

    async def update_form(self, form_id: PydanticObjectId, form: StandardForm):
        form_document = await self.one(FormRow.form_id == _oid(form_id))
        form_document.fields = form.fields
        if form.hidden_fields is not None:
            form_document.hidden_fields = form.hidden_fields
        form_document.title = form.title
        form_document.logo = form.logo
        form_document.cover_image = form.cover_image
        form_document.description = form.description
        form_document.welcome_page = form.welcome_page
        form_document.thankyou_page = form.thankyou_page
        form_document.theme = form.theme
        form_document.consent = form.consent if form.consent else form_document.consent
        form_document.settings = (
            form.settings if form.settings else form_document.settings
        )
        return await self.upsert(form_document)

    async def get_form_document_by_id(self, form_id: str):
        return await self.one(FormRow.form_id == form_id)

    async def get_latest_version_of_form(self, form_id: PydanticObjectId):
        return await self.one_of(
            FormVersionRow,
            FormVersionsDocument,
            FormVersionRow.form_id == _oid(form_id),
            order_by=(FormVersionRow.version.desc(), FormVersionRow.id),
        )

    async def get_form_by_by_version(
        self, form_id: PydanticObjectId, version: FormVersion | int
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
        return await self.upsert(new_form_version, row=FormVersionRow)

    async def get_form_by_id(self, form_id: PydanticObjectId):
        return await self.one(FormRow.form_id == _oid(form_id))

    async def update_form_actions(
        self,
        form_id: PydanticObjectId,
        action_id: PydanticObjectId,
        form: StandardForm,
        payload: FormActionsDto,
    ):
        secrets = form.secrets[str(action_id)]
        for secret in secrets:
            if secret.name == payload.name:
                secret.value = payload.value
        form.secrets[str(action_id)] = secrets
        return await self.upsert(form)


class PostgresWorkspaceFormRepository(PostgresRepositoryBase):
    row = WorkspaceFormRow
    document = WorkspaceFormDocument

    def __init__(self, session_factory, responder_groups):
        super().__init__(session_factory)
        self._groups = responder_groups  # routed ResponderGroupsRepository

    async def find_workspace_form(
        self, workspace_id: PydanticObjectId, form_id: str
    ) -> Optional[WorkspaceFormDocument]:
        return await self.one(
            WorkspaceFormRow.form_id == form_id,
            WorkspaceFormRow.workspace_id == _oid(workspace_id),
        )

    async def find_first_by_form_id(
        self, form_id: str
    ) -> Optional[WorkspaceFormDocument]:
        return await self.one(WorkspaceFormRow.form_id == form_id)

    async def list_in_workspace(
        self, workspace_id: PydanticObjectId
    ) -> List[WorkspaceFormDocument]:
        return await self.many(WorkspaceFormRow.workspace_id == _oid(workspace_id))

    async def save(
        self, workspace_form: WorkspaceFormDocument
    ) -> WorkspaceFormDocument:
        return await self.upsert(workspace_form)

    async def update(
        self, item_id: str, item: WorkspaceFormDocument
    ) -> WorkspaceFormDocument:
        if await self.one(WorkspaceFormRow.id == _oid(item_id)) is None:
            raise HTTPException(HTTPStatus.NOT_FOUND, "Form not found in ")
        return await self.upsert(item)

    async def save_workspace_form(
        self,
        workspace_id: PydanticObjectId,
        form_id: str,
        user_id: str,
        workspace_form_settings: WorkspaceFormSettings,
    ) -> WorkspaceFormDocument:
        workspace_form = await self.one(
            WorkspaceFormRow.workspace_id == _oid(workspace_id),
            WorkspaceFormRow.form_id == form_id,
            WorkspaceFormRow.user_id == user_id,
        )
        if not workspace_form:
            workspace_form = WorkspaceFormDocument(
                workspace_id=workspace_id, form_id=form_id, user_id=user_id
            )
        workspace_form.settings = workspace_form_settings
        return await self.upsert(workspace_form)

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
        self, workspace_id: PydanticObjectId, query: str, is_admin=True
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
        workspace_id: PydanticObjectId,
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
            # private forms stay visible to responders their groups admit
            admitted = await self._groups.get_form_ids_accessible_to(
                [wf["form_id"] for wf in workspace_forms], user.sub
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
        workspace_id: PydanticObjectId,
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
        self, workspace_id: PydanticObjectId, custom_url: str
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
        self, workspace_id: PydanticObjectId, form_id: str
    ):
        workspace_form = await self.find_workspace_form(workspace_id, form_id)
        if not workspace_form:
            raise HTTPException(status_code=404, content="Form not found in Workspace")
        await self.delete_by_id(workspace_form.id)
        return workspace_form

    async def check_is_form_imported_in_other_workspace(
        self, workspace_id: PydanticObjectId, form_id: str
    ):
        for workspace_form in await self.many(WorkspaceFormRow.form_id == form_id):
            if workspace_form.workspace_id != workspace_id:
                raise HTTPException(
                    status_code=HTTPStatus.CONFLICT,
                    content="Form has already been imported to another workspace",
                )

    async def get_form_ids_imported_by_user(
        self, workspace_id: PydanticObjectId, user_id: str
    ):
        forms = await self.many(
            WorkspaceFormRow.workspace_id == _oid(workspace_id),
            WorkspaceFormRow.user_id == user_id,
        )
        return [form.form_id for form in forms]

    async def get_form_ids_in_workspaces_and_imported_by_user(
        self, workspace_ids: List[PydanticObjectId], user: User
    ):
        forms = await self.many(
            or_(
                WorkspaceFormRow.workspace_id.in_([_oid(i) for i in workspace_ids]),
                WorkspaceFormRow.user_id == user.id,
            ),
            _text(self._settings()["provider"]).is_distinct_from("self"),
        )
        return [form.form_id for form in forms]

    async def delete_forms(self, form_ids):
        return await self.delete_where(WorkspaceFormRow.form_id.in_(list(form_ids)))

    async def get_workspace_forms_form_ids(self, form_ids: List[str]):
        return await self.many(WorkspaceFormRow.form_id.in_(form_ids))

    async def check_if_form_exists_in_workspace(
        self, workspace_id: PydanticObjectId, form_id: str
    ):
        workspace_form = await self.find_workspace_form(workspace_id, form_id)
        return True if workspace_form is not None else False


class PostgresWorkspaceConsentRepo(PostgresRepositoryBase):
    row = WorkspaceConsentRow
    document = WorkspaceConsentDocument

    async def get_workspace_consents(self, workspace_id: PydanticObjectId):
        return await self.many(WorkspaceConsentRow.workspace_id == _oid(workspace_id))

    async def create_workspace_consent(
        self, workspace_id: PydanticObjectId, consent: ConsentCamelModel
    ):
        consent_document = WorkspaceConsentDocument(**consent.model_dump(mode="json"))
        consent_document.workspace_id = workspace_id
        return await self.upsert(consent_document)


class PostgresFormTemplateRepository(PostgresRepositoryBase):
    row = FormTemplateRow
    document = FormTemplateDocument

    def __init__(self, session_factory, workspaces):
        super().__init__(session_factory)
        self._workspaces = workspaces  # routed WorkspaceRepository

    async def get_templates_with_creator(
        self,
        v2: Optional[bool] = None,
        workspace_id: PydanticObjectId = None,
        template_id: PydanticObjectId = None,
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
        templates = [from_canonical_document(doc) for doc in docs]
        origins = {
            t["imported_from"] for t in templates if t.get("imported_from") is not None
        }
        titles = {}
        if origins:
            for workspace in await self._workspaces.get_workspace_by_ids(list(origins)):
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

    async def get_template_by_id(self, template_id: PydanticObjectId):
        return await self.one(FormTemplateRow.id == _oid(template_id))

    async def get_template_by_workspace_id_n_template_id(
        self, workspace_id: PydanticObjectId, template_id: PydanticObjectId
    ):
        return await self.one(
            FormTemplateRow.id == _oid(template_id),
            FormTemplateRow.workspace_id == _oid(workspace_id),
        )

    async def get_template_by_id_with_creator(
        self, workspace_id: PydanticObjectId, template_id: PydanticObjectId
    ):
        templates = await self.get_templates_with_creator(
            workspace_id=workspace_id, template_id=template_id
        )
        if len(templates) > 0:
            return templates[0]
        raise HTTPException(HTTPStatus.NOT_FOUND, content=MESSAGE_NOT_FOUND)

    async def import_template_to_workspace(
        self, workspace_id: PydanticObjectId, template_id: PydanticObjectId
    ):
        template = await self.get_template_by_id(template_id)
        imported_template = FormTemplateDocument(**template.model_dump(mode="json"))
        imported_template.id = None
        imported_template.imported_from = template.workspace_id
        imported_template.workspace_id = workspace_id
        imported_template.settings = StandardTemplateSetting()
        return await self.upsert(imported_template)

    async def create_new_template(
        self,
        workspace_id: PydanticObjectId,
        template_body: StandardFormTemplate,
        user: User,
    ):
        template = FormTemplateDocument(**template_body.model_dump(mode="json"))
        template.workspace_id = workspace_id
        template.created_by = user.id
        return await self.upsert(template)

    async def update_template(
        self, template_id: PydanticObjectId, template_body: StandardFormTemplate
    ):
        template = await self.get_template_by_id(template_id)
        template.fields = template_body.fields
        template.settings = template_body.settings
        template.title = template_body.title
        template.description = template_body.description
        template.button_text = template_body.button_text
        template.logo = template_body.logo
        template.cover_image = template_body.cover_image
        return await self.upsert(template)

    async def save(self, template: FormTemplateDocument) -> FormTemplateDocument:
        return await self.upsert(template)

    async def delete_template(self, template_id: PydanticObjectId):
        template = await self.get_template_by_id(template_id)
        if not template:
            raise HTTPException(HTTPStatus.NOT_FOUND, "Template not found")
        await self.delete_by_id(template.id)
        return str(template_id)


class PostgresMediaLibraryRepository(PostgresRepositoryBase):
    row = MediaLibraryRow
    document = MediaLibraryDocument

    async def get_media_library_by_worksapce_id(
        self, workspace_id: str, media_query: str
    ):
        where = [MediaLibraryRow.workspace_id == workspace_id]
        if media_query is not None:
            where.append(MediaLibraryRow.media_name.op("~*")(media_query))
        return await self.many(
            *where, order_by=(MediaLibraryRow.created_at.desc(), MediaLibraryRow.id)
        )

    async def get_single_media_from_workspace_library(
        self, workspace_id: str, media_id: PydanticObjectId
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
            media_id=PydanticObjectId(),
            workspace_id=workspace_id,
            media_type=media_type,
            media_name=media_name,
            media_url=media_url,
            s3_key=s3_key,
        )
        return await self.upsert(media)

    async def delete_media_from_library(
        self, workspace_id: str, media_id: PydanticObjectId
    ):
        media = await self.get_single_media_from_workspace_library(
            workspace_id, media_id
        )
        await self.delete_by_id(
            media.id
        )  # AttributeError when missing, as the original
        return media_id
