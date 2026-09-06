"""Postgres twins of the responses-group repositories.

Within the group (form_responses ⋈ responses_deletion_requests ⋈
workspace_responder ⋈ workspace_tags, responder_group ⋈ members ⋈ forms) the
Mongo ``$lookup``s are SQL joins. Into the forms group (a form's title, the
workspace that imported it) they *compose* through the routed forms
repositories — see plans/postgres-consolidation.md §4 — restricted to the
form ids those repositories know, because the Mongo ``$unwind`` drops
responses whose form is gone.
"""

import json
import re
from http import HTTPStatus
from typing import Any, Dict, Iterable, List, Optional, Set
from uuid import uuid4

from beanie import PydanticObjectId
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import apaginate
from pydantic import EmailStr
from sqlalchemy import and_, func, literal, or_, select

from backend.app.exceptions import HTTPException
from backend.app.models.dtos.response_group_dto import ResponderGroupDto
from backend.app.models.filter_queries.form_responses import FormResponseFilterQuery
from backend.app.models.filter_queries.sort import SortOrder, SortRequest
from backend.app.repositories.postgres.forms import _fold, _oid, _sort_terms, _text
from backend.app.schemas.responder_group import (
    ResponderGroupDocument,
    ResponderGroupFormDocument,
    ResponderGroupMemberDocument,
)
from backend.app.schemas.standard_form_response import (
    DeletionRequestStatus,
    FormResponseDeletionRequest,
    FormResponseDocument,
)
from backend.app.schemas.workspace_responder import (
    WorkspaceResponderDocument,
    WorkspaceTags,
)
from backend.db.models import (
    ResponseDeletionRequestRow,
    FormResponseRow,
    ResponderGroupFormRow,
    ResponderGroupMemberRow,
    ResponderGroupRow,
    WorkspaceResponderRow,
    WorkspaceTagRow,
)
from common.constants import MESSAGE_FORBIDDEN
from common.db import (
    PostgresRepositoryBase,
    derived_object_id,
    from_canonical_document,
    from_row_doc,
    to_bson_dict,
)
from common.models.standard_form import StandardFormResponse, StandardFormResponseAnswer
from common.models.user import User
from common.services.crypto_service import crypto_service
from camel_converter import to_camel, to_snake


def _filter_terms(doc, filter_query) -> list:
    """``create_filter_pipeline(filter_object=...)``: each set field is a
    case-insensitive regex on its camelCase or snake_case key."""
    if not filter_query:
        return []
    matching = filter_query.model_dump(exclude_unset=True, exclude_none=True)
    return [
        or_(
            _text(doc[to_camel(key)]).op("~*")(value),
            _text(doc[to_snake(key)]).op("~*")(value),
        )
        for key, value in matching.items()
    ]


class PostgresFormResponseRepository(PostgresRepositoryBase):
    row = FormResponseRow
    document = FormResponseDocument

    def __init__(self, session_factory, form_repo, workspace_form_repo):
        super().__init__(session_factory)
        self._forms = form_repo  # routed FormRepository
        self._workspace_forms = workspace_form_repo  # routed WorkspaceFormRepository

    # -- composition over the forms group ---------------------------------
    async def _form_titles(self, form_ids: List[str]) -> Dict[str, Any]:
        """form_id -> title for the forms that exist (``$lookup forms`` + ``$unwind``)."""
        forms = await self._forms.get_forms_by_form_ids(list(form_ids))
        return {form.form_id: form.title for form in forms}

    async def _form_importers(self, form_ids: List[str]) -> Dict[str, str]:
        """form_id -> importing user (``$lookup workspace_forms`` + ``$unwind``)."""
        rows = await self._workspace_forms.get_workspace_forms_form_ids(list(form_ids))
        importers: Dict[str, str] = {}
        for workspace_form in rows:
            importers.setdefault(workspace_form.form_id, workspace_form.user_id)
        return importers

    # -- listings -----------------------------------------------------------
    async def get_form_responses(
        self,
        form_ids,
        data_owner_identifier: Optional[str] = None,
        filter_query: FormResponseFilterQuery = None,
        sort: SortRequest = None,
    ) -> Page:
        titles = await self._form_titles(form_ids)
        dr = ResponseDeletionRequestRow
        where = [
            FormResponseRow.form_id.in_(list(titles)),
            FormResponseRow.doc.has_key("answers"),
            *_filter_terms(FormResponseRow.doc, filter_query),
        ]
        if data_owner_identifier is not None:
            where.append(FormResponseRow.data_owner_identifier == data_owner_identifier)
        # $arrayElemAt [deletion_request.status, 0]: the first request, in natural order
        first_request = (
            select(dr.doc)
            .where(dr.response_id == FormResponseRow.response_id)
            .order_by(dr.created_at, dr.id)
            .limit(1)
            .correlate(FormResponseRow)
            .scalar_subquery()
        )
        stmt = (
            select(FormResponseRow.doc, first_request)
            .where(*where)
            .order_by(
                *_sort_terms(
                    FormResponseRow.doc,
                    sort,
                    (FormResponseRow.created_at.desc(), FormResponseRow.id),
                )
            )
        )

        async def transform(items):
            responses = []
            for doc, request_doc in items:
                response = from_canonical_document(doc)
                response["form_title"] = titles[response["form_id"]]
                if request_doc is not None:  # $arrayElemAt: unset without a request
                    response["status"] = from_canonical_document(request_doc).get(
                        "status"
                    )
                responses.append(response)
            return responses

        async with self._session() as session:
            return await apaginate(session, stmt, transformer=transform, unique=False)

    async def get_workspace_responders(
        self,
        form_ids: List[str],
        filter_query: FormResponseFilterQuery = None,
        sort: SortRequest = None,
    ):
        r, dr, wr = FormResponseRow, ResponseDeletionRequestRow, WorkspaceResponderRow
        grouped = (
            select(
                r.data_owner_identifier.label("email"),
                func.count().label("responses"),
                func.array_agg(r.response_id).label("response_ids"),
            )
            .where(r.form_id.in_(list(form_ids)), r.data_owner_identifier.is_not(None))
            .group_by(r.data_owner_identifier)
            .subquery("grouped")
        )
        deletion_requests = (
            select(func.count())
            .where(dr.response_id == func.any(grouped.c.response_ids))
            .correlate(grouped)
            .scalar_subquery()
        )
        stmt = (
            select(
                grouped.c.email,
                grouped.c.responses,
                deletion_requests.label("deletion_requests"),
                wr.doc,
            )
            .outerjoin(wr, wr.email == grouped.c.email)  # any workspace, as the $lookup
            .order_by(grouped.c.email, wr.created_at, wr.id)
        )
        # create_filter_pipeline(..., default_sort=False): filters only, no sort
        matching = (
            filter_query.model_dump(exclude_unset=True, exclude_none=True)
            if filter_query
            else {}
        )
        for key, value in matching.items():
            keys = {to_camel(key), to_snake(key)}
            if "email" in keys:
                stmt = stmt.where(grouped.c.email.op("~*")(value))
            else:  # the projected document has no such field
                stmt = stmt.where(literal(False))

        async def transform(items):
            responders = []
            tag_ids: Set[str] = set()
            for email, responses, deletions, responder_doc in items:
                responder = {
                    "email": email,
                    "responses": responses,
                    "deletion_requests": deletions,
                }
                if responder_doc is not None:
                    raw = from_canonical_document(responder_doc)
                    _fold(responder, raw, {"tags": "tags", "metadata": "metadata"})
                responders.append(responder)
                for tag in responder.get("tags") or []:
                    tag_ids.add(_oid(tag))
            tags = {}
            if tag_ids:
                async with self._session() as session:
                    docs = (
                        (
                            await session.execute(
                                select(WorkspaceTagRow.doc).where(
                                    WorkspaceTagRow.id.in_(tag_ids)
                                )
                            )
                        )
                        .scalars()
                        .all()
                    )
                for doc in docs:
                    tag = from_canonical_document(doc)
                    tags[_oid(tag["_id"])] = tag
            for responder in responders:  # $lookup workspace_tags: docs, [] when none
                responder["tags"] = [
                    tags[_oid(t)]
                    for t in (responder.get("tags") or [])
                    if _oid(t) in tags
                ]
            return responders

        async with self._session() as session:
            return await apaginate(session, stmt, transformer=transform, unique=False)

    async def get_deletion_requests(
        self,
        form_ids,
        data_owner_identifier: Optional[str] = None,
        filter_query: FormResponseFilterQuery = None,
        sort: SortRequest = None,
    ):
        """DeletionRequestsRepository.get_deletion_requests, composed."""
        titles = await self._form_titles(form_ids)
        importers = await self._form_importers(list(titles))
        known = [f for f in titles if f in importers]  # both $unwinds must match
        dr, r = ResponseDeletionRequestRow, FormResponseRow
        where = [dr.form_id.in_(known), *_filter_terms(dr.doc, filter_query)]
        if data_owner_identifier is not None:
            where.append(dr.data_owner_identifier == data_owner_identifier)
        response_doc = (
            select(r.doc)
            .where(r.response_id == dr.response_id)
            .order_by(r.created_at, r.id)
            .limit(1)
            .correlate(dr)
            .scalar_subquery()
        )
        stmt = (
            select(dr.doc, response_doc)
            .where(*where)
            .order_by(*_sort_terms(dr.doc, sort, (dr.created_at, dr.id)))
        )

        async def transform(items):
            requests = []
            for doc, response in items:
                request = from_canonical_document(doc)
                request["form_title"] = titles[request["form_id"]]
                request["form_imported_by"] = importers[request["form_id"]]
                if response is not None:  # $arrayElemAt: unset without a response
                    request["submission_uuid"] = from_canonical_document(response).get(
                        "submission_uuid"
                    )
                requests.append(request)
            return requests

        async with self._session() as session:
            return await apaginate(session, stmt, transformer=transform, unique=False)

    async def list(
        self,
        form_ids: List[str],
        request_for_deletion: bool,
        filter_query: FormResponseFilterQuery = None,
        sort: SortRequest = None,
        data_subjects: bool = None,
    ) -> Page:
        if data_subjects:
            return await self.get_workspace_responders(
                form_ids=form_ids, filter_query=filter_query, sort=sort
            )
        elif request_for_deletion:
            return await self.get_deletion_requests(
                form_ids, filter_query=filter_query, sort=sort
            )
        else:
            return await self.get_form_responses(
                form_ids, filter_query=filter_query, sort=sort
            )

    async def get_user_submissions(
        self, form_ids, user: User, request_for_deletion: bool = False
    ):
        if request_for_deletion:
            return await self.get_deletion_requests(
                form_ids=form_ids, data_owner_identifier=user.sub
            )
        else:
            return await self.get_form_responses(
                form_ids, data_owner_identifier=user.sub
            )

    # -- counts -------------------------------------------------------------
    async def _counts_by_form(self, row, *where) -> Dict[str, int]:
        async with self._session() as session:
            rows = (
                await session.execute(
                    select(row.form_id, func.count())
                    .where(*where)
                    .group_by(row.form_id)
                )
            ).all()
        return {form_id: n for form_id, n in rows}

    async def count_responses_with_answers_by_form_ids(
        self, form_ids: List[str]
    ) -> Dict[str, int]:
        return await self._counts_by_form(
            FormResponseRow,
            FormResponseRow.form_id.in_(form_ids),
            FormResponseRow.doc.has_key("answers"),
        )

    async def count_deletion_requests_by_form_ids(
        self, form_ids: List[str]
    ) -> Dict[str, int]:
        return await self._counts_by_form(
            ResponseDeletionRequestRow,
            ResponseDeletionRequestRow.form_id.in_(form_ids),
        )

    async def count_responses_for_form_ids(self, form_ids: List[str]) -> int:
        return await self.count(FormResponseRow.form_id.in_(form_ids))

    async def get_deletion_requests_count_in_workspace(self, form_ids: List[str]):
        dr = ResponseDeletionRequestRow
        in_forms = dr.form_id.in_(form_ids)

        async def count_where(*where):
            async with self._session() as session:
                return (
                    await session.execute(
                        select(func.count()).select_from(dr).where(*where)
                    )
                ).scalar_one()

        counts = {
            "success": await count_where(
                in_forms, dr.status == DeletionRequestStatus.SUCCESS.value
            ),
            "pending": await count_where(
                in_forms, dr.status == DeletionRequestStatus.PENDING.value
            ),
            "total": await count_where(in_forms),
        }
        # $count emits no document for zero matches; $arrayElemAt then unsets the field
        return {k: v for k, v in counts.items() if v}

    # -- BaseRepository stubs ---------------------------------------------
    async def get(self, form_id: str, response_id: str):
        pass

    async def add(self, item: FormResponseDocument):
        pass

    async def update(self, item_id: str, item: FormResponseDocument):
        pass

    async def delete(self, item_id: str, provider):
        pass

    # -- plain reads and writes ------------------------------------------------
    async def list_recent_by_form_id(
        self, form_id: str, limit: int
    ) -> List[FormResponseDocument]:
        return await self.many(
            FormResponseRow.form_id == form_id,
            order_by=(FormResponseRow.created_at.desc(), FormResponseRow.id),
            limit=limit,
        )

    async def list_deletion_requests_for_form_ids(
        self, form_ids: List[str]
    ) -> List[FormResponseDeletionRequest]:
        return await self.many(
            ResponseDeletionRequestRow.form_id.in_(form_ids),
            row=ResponseDeletionRequestRow,
            document=FormResponseDeletionRequest,
        )

    async def list_by_form_id(self, form_id: str) -> List[FormResponseDocument]:
        return await self.many(FormResponseRow.form_id == form_id)

    async def save(self, response: FormResponseDocument) -> FormResponseDocument:
        return await self.upsert(response)

    async def find_deletion_request_by_response_id(
        self, response_id: str
    ) -> Optional[FormResponseDeletionRequest]:
        return await self.one_of(
            ResponseDeletionRequestRow,
            FormResponseDeletionRequest,
            ResponseDeletionRequestRow.response_id == response_id,
        )

    async def add_deletion_request(
        self, response: FormResponseDocument, response_id: str
    ) -> FormResponseDeletionRequest:
        return await self.upsert(
            FormResponseDeletionRequest(
                form_id=response.form_id,
                response_id=response_id,
                dataOwnerIdentifier=response.dataOwnerIdentifier,
                anonymous_identity=response.anonymous_identity,
                provider=response.provider,
                deleted_at=None,
            ),
            row=ResponseDeletionRequestRow,
        )

    async def delete_by_form_id_except(
        self, form_id: str, keep_response_ids: List[str]
    ):
        return await self.delete_where(
            FormResponseRow.form_id == form_id,
            FormResponseRow.response_id.not_in(list(keep_response_ids)),
        )

    async def mark_deletion_requests_success_except(
        self, form_id: str, provider: str, keep_response_ids: List[str], now
    ) -> int:
        dr = ResponseDeletionRequestRow
        requests = await self.many(
            dr.form_id == form_id,
            dr.provider == provider,
            dr.response_id.not_in(list(keep_response_ids)),
            row=dr,
            document=FormResponseDeletionRequest,
        )
        modified = 0
        for request in requests:
            if (
                request.status != DeletionRequestStatus.SUCCESS
                or request.updated_at != now
            ):
                modified += 1
            request.status = DeletionRequestStatus.SUCCESS
            request.updated_at = now
        await self.upsert_many(requests, row=dr)
        return modified

    async def delete_by_form_id(self, form_id):
        return await self.delete_where(FormResponseRow.form_id == form_id)

    async def delete_deletion_requests(self, form_id: str):
        return await self.delete_where(
            ResponseDeletionRequestRow.form_id == form_id,
            row=ResponseDeletionRequestRow,
        )

    async def delete_by_form_ids(self, form_ids):
        return await self.delete_where(FormResponseRow.form_id.in_(list(form_ids)))

    async def delete_deletion_requests_by_form_ids(self, form_ids):
        return await self.delete_where(
            ResponseDeletionRequestRow.form_id.in_(list(form_ids)),
            row=ResponseDeletionRequestRow,
        )

    async def save_form_response(
        self,
        form_id: PydanticObjectId,
        response: StandardFormResponse,
        workspace_id: PydanticObjectId,
    ):
        response_document = FormResponseDocument(**response.model_dump(mode="json"))
        response_document.submission_uuid = str(uuid4())
        if workspace_id:
            for k, v in response_document.answers.items():
                if type(v) == StandardFormResponseAnswer:
                    response_document.answers[k] = v.model_dump(mode="json")
            response_document.answers = crypto_service.encrypt(
                workspace_id=workspace_id,
                form_id=form_id,
                data=json.dumps(response_document.answers),
            )
            if isinstance(response_document.hidden_fields, dict):
                response_document.hidden_fields = crypto_service.encrypt(
                    workspace_id=workspace_id,
                    form_id=form_id,
                    data=json.dumps(response_document.hidden_fields),
                )
        response_document.form_id = str(form_id)
        response_document.provider = "self"
        return await self.upsert(response_document)

    async def patch_form_response(
        self,
        form_id: PydanticObjectId,
        response_id: PydanticObjectId,
        response: StandardFormResponse,
        workspace_id: PydanticObjectId,
        user=User,
    ):
        response_document = await self.one(
            FormResponseRow.response_id == _oid(response_id)
        )
        if not response_document.dataOwnerIdentifier != user.sub:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN, content=MESSAGE_FORBIDDEN
            )
        for k, v in response.answers.items():
            if type(v) == StandardFormResponseAnswer:
                response_document.answers[k] = v.model_dump(mode="json")
            response_document.answers = crypto_service.encrypt(
                workspace_id=workspace_id,
                form_id=form_id,
                data=json.dumps(response_document.answers),
            )
        return await self.upsert(response_document)

    async def delete_form_response(self, form_id: PydanticObjectId, response_id: str):
        await self.delete_where(
            FormResponseRow.form_id == _oid(form_id),
            FormResponseRow.response_id == response_id,
        )
        deletion_request = await self.one_of(
            ResponseDeletionRequestRow,
            FormResponseDeletionRequest,
            ResponseDeletionRequestRow.form_id == _oid(form_id),
            ResponseDeletionRequestRow.response_id == response_id,
        )
        if deletion_request:
            deletion_request.status = DeletionRequestStatus.SUCCESS
            await self.upsert(deletion_request, row=ResponseDeletionRequestRow)
        return response_id

    async def get_all_expiring_responses(self):
        return await self.many(FormResponseRow.expiration_type.in_(["date", "days"]))

    async def delete_response(self, response_id: str):
        await self.delete_one_where(FormResponseRow.response_id == response_id)
        return response_id

    async def get_response(self, response_id: str):
        return await self.one(FormResponseRow.response_id == response_id)

    async def get_by_submission_uuid(self, submission_uuid: str):
        return await self.one(FormResponseRow.submission_uuid == submission_uuid)

    async def verify_response_exists_in_workspace(
        self, workspace_id: PydanticObjectId, response_id: str
    ):
        response = await self.one(FormResponseRow.response_id == response_id)
        workspace_form = (
            None
            if response is None
            else await self._workspace_forms.find_workspace_form(
                workspace_id, response.form_id
            )
        )
        if workspace_form is None:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                content="Response not found in workspace",
            )


class PostgresWorkspaceRespondersRepository(PostgresRepositoryBase):
    row = WorkspaceResponderRow
    document = WorkspaceResponderDocument

    async def create_workspace_tag(self, workspace_id: PydanticObjectId, title: str):
        workspace_tag = await self.one_of(
            WorkspaceTagRow,
            WorkspaceTags,
            WorkspaceTagRow.workspace_id == _oid(workspace_id),
            WorkspaceTagRow.title == title,
        )
        if not workspace_tag:
            workspace_tag = WorkspaceTags(workspace_id=workspace_id, title=title)
        return await self.upsert(workspace_tag, row=WorkspaceTagRow)

    async def get_workspace_tags(self, workspace_id: PydanticObjectId):
        return await self.many(
            WorkspaceTagRow.workspace_id == _oid(workspace_id),
            row=WorkspaceTagRow,
            document=WorkspaceTags,
        )

    async def get_responder_by_email_and_workspace_id(
        self, workspace_id: PydanticObjectId, email: str
    ):
        workspace_responder = await self.one(
            WorkspaceResponderRow.workspace_id == _oid(workspace_id),
            WorkspaceResponderRow.email == email,
        )
        if not workspace_responder:
            workspace_responder = WorkspaceResponderDocument(
                workspace_id=workspace_id, email=email
            )
        return await self.upsert(workspace_responder)


class PostgresResponderGroupsRepository(PostgresRepositoryBase):
    row = ResponderGroupRow
    document = ResponderGroupDocument

    @staticmethod
    def member(
        group_id: PydanticObjectId, identifier: str
    ) -> ResponderGroupMemberDocument:
        return ResponderGroupMemberDocument(
            id=derived_object_id("responder_group_member", group_id, identifier),
            group_id=group_id,
            identifier=identifier,
        )

    @staticmethod
    def link(group_id: PydanticObjectId, form_id: str) -> ResponderGroupFormDocument:
        return ResponderGroupFormDocument(
            id=derived_object_id("responder_group_form", group_id, form_id),
            group_id=group_id,
            form_id=form_id,
        )

    async def _members(self, *where) -> List[ResponderGroupMemberDocument]:
        return await self.many(
            *where, row=ResponderGroupMemberRow, document=ResponderGroupMemberDocument
        )

    async def _links(self, *where) -> List[ResponderGroupFormDocument]:
        return await self.many(
            *where, row=ResponderGroupFormRow, document=ResponderGroupFormDocument
        )

    async def create_group(
        self,
        workspace_id: PydanticObjectId,
        name: str,
        description: Optional[str] = None,
        regex: Optional[str] = None,
    ):
        if description and len(description) > 280:
            return {"message": "description should be less than 280 characters"}
        return await self.upsert(
            ResponderGroupDocument(
                name=name,
                workspace_id=workspace_id,
                description=description,
                regex=regex,
            )
        )

    async def update_group(
        self,
        workspace_id: PydanticObjectId,
        name: Optional[str] = None,
        description: Optional[str] = None,
        emails: List[EmailStr] = None,
        group_id: PydanticObjectId = None,
        regex: Optional[str] = None,
    ):
        responder_group = await self.get_group_in_workspace(workspace_id, group_id)
        if emails and len(emails) != 0:
            await self.delete_where(
                ResponderGroupMemberRow.group_id == _oid(group_id),
                row=ResponderGroupMemberRow,
            )
            await self.upsert_many(
                [self.member(group_id, email) for email in set(emails)],
                row=ResponderGroupMemberRow,
            )
        if responder_group:
            if name:
                responder_group.name = name
            if description:
                responder_group.description = description
            responder_group.regex = regex
        return await self.upsert(responder_group)

    async def get_group_in_workspace(
        self, workspace_id: PydanticObjectId, group_id: PydanticObjectId
    ):
        return await self.one(
            ResponderGroupRow.workspace_id == _oid(workspace_id),
            ResponderGroupRow.id == _oid(group_id),
        )

    async def add_emails_to_group(
        self, group_id: PydanticObjectId, emails: List[EmailStr]
    ):
        emails = list(set(emails))
        existing = {
            member.identifier
            for member in await self._members(
                ResponderGroupMemberRow.group_id == _oid(group_id),
                ResponderGroupMemberRow.identifier.in_(emails),
            )
        }
        new_members = [self.member(group_id, e) for e in emails if e not in existing]
        if new_members:
            await self.upsert_many(new_members, row=ResponderGroupMemberRow)

    async def remove_emails_from_group(
        self, group_id: PydanticObjectId, emails: List[EmailStr]
    ):
        await self.delete_where(
            ResponderGroupMemberRow.group_id == _oid(group_id),
            ResponderGroupMemberRow.identifier.in_(list(emails)),
            row=ResponderGroupMemberRow,
        )

    async def _projected(self, groups: List[ResponderGroupDocument]) -> List[dict]:
        """The $project of get_emails_in_group / get_groups_in_workspace."""
        ids = [_oid(g.id) for g in groups]
        members = await self._members(ResponderGroupMemberRow.group_id.in_(ids))
        links = await self._links(ResponderGroupFormRow.group_id.in_(ids))
        out = []
        for group in groups:
            out.append(
                {
                    "_id": group.id,
                    "name": group.name,
                    "workspace_id": group.workspace_id,
                    "emails": [m.identifier for m in members if m.group_id == group.id],
                    "description": group.description,
                    "regex": group.regex,
                    "forms": [l.form_id for l in links if l.group_id == group.id],
                }
            )
        return out

    async def get_emails_in_group(self, group_id: PydanticObjectId):
        group = await self.one(ResponderGroupRow.id == _oid(group_id))
        if group is None:
            return None
        return (await self._projected([group]))[0]

    async def remove_responder_group(self, group_id: PydanticObjectId):
        await self.delete_by_id(group_id)
        await self.delete_where(
            ResponderGroupMemberRow.group_id == _oid(group_id),
            row=ResponderGroupMemberRow,
        )
        await self.delete_where(
            ResponderGroupFormRow.group_id == _oid(group_id), row=ResponderGroupFormRow
        )

    async def get_groups_in_workspace(self, workspace_id: PydanticObjectId):
        groups = await self.many(ResponderGroupRow.workspace_id == _oid(workspace_id))
        return [ResponderGroupDto(**row) for row in await self._projected(groups)]

    async def get_groups_by_form_ids(
        self, form_ids: List[str]
    ) -> Dict[str, List[dict]]:
        links = await self._links(ResponderGroupFormRow.form_id.in_(list(form_ids)))
        groups = {
            group.id: to_bson_dict(group)
            for group in await self.many(
                ResponderGroupRow.id.in_([_oid(l.group_id) for l in links] or ["-"])
            )
        }
        by_form: Dict[str, List[dict]] = {form_id: [] for form_id in form_ids}
        for link in links:
            if link.group_id in groups:
                by_form.setdefault(link.form_id, []).append(groups[link.group_id])
        return by_form

    async def get_form_ids_accessible_to(
        self, form_ids: List[str], identifier: str
    ) -> Set[str]:
        links = await self._links(ResponderGroupFormRow.form_id.in_(list(form_ids)))
        group_ids = [_oid(g) for g in {link.group_id for link in links}]
        if not group_ids:
            return set()
        member_of = {
            member.group_id
            for member in await self._members(
                ResponderGroupMemberRow.group_id.in_(group_ids),
                ResponderGroupMemberRow.identifier == identifier,
            )
        }
        for group in await self.many(ResponderGroupRow.id.in_(group_ids)):
            if not group.regex:
                continue
            try:
                if re.search(group.regex, identifier):
                    member_of.add(group.id)
            except re.error:
                continue
        return {link.form_id for link in links if link.group_id in member_of}

    async def add_group_to_form(self, form_id: str, group_id: PydanticObjectId):
        existing = await self._links(
            ResponderGroupFormRow.form_id == form_id,
            ResponderGroupFormRow.group_id == _oid(group_id),
        )
        if not existing:
            return await self.upsert(
                self.link(group_id, form_id), row=ResponderGroupFormRow
            )

    async def add_groups_to_form(self, form_id: str, group_ids: List[PydanticObjectId]):
        ids_to_add = group_ids
        existing_groups = await self._links(ResponderGroupFormRow.form_id == form_id)
        ids_to_remove = [group.group_id for group in existing_groups]
        for group_id in list(ids_to_remove):
            if group_id in ids_to_add:
                ids_to_remove.remove(group_id)
                ids_to_add.remove(group_id)
        for group_id in ids_to_remove:
            await self.remove_group_from_form(form_id, group_id)
        for group_id in ids_to_add:
            await self.add_group_to_form(form_id, group_id)
        return await self._links(ResponderGroupFormRow.form_id == form_id)

    async def remove_group_from_form(self, form_id: str, group_id: PydanticObjectId):
        await self.delete_one_where(
            ResponderGroupFormRow.form_id == form_id,
            ResponderGroupFormRow.group_id == _oid(group_id),
            row=ResponderGroupFormRow,
        )

    async def delete_workspace_form_groups(self, form_id: str):
        await self.delete_where(
            ResponderGroupFormRow.form_id == form_id, row=ResponderGroupFormRow
        )

    async def delete_responder_groups(self, workspace_ids: List[PydanticObjectId]):
        groups = await self.many(
            ResponderGroupRow.workspace_id.in_([_oid(w) for w in workspace_ids])
        )
        group_ids = [_oid(group.id) for group in groups] or ["-"]
        await self.delete_where(
            ResponderGroupFormRow.group_id.in_(group_ids), row=ResponderGroupFormRow
        )
        await self.delete_where(
            ResponderGroupMemberRow.group_id.in_(group_ids), row=ResponderGroupMemberRow
        )
        await self.delete_where(ResponderGroupRow.id.in_(group_ids))
