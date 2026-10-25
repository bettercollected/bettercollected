from datetime import datetime
from typing import Dict, List, Optional

from beanie import PydanticObjectId
from beanie.odm.enums import SortDirection
from beanie.odm.utils.dump import get_dict
from beanie.odm.utils.parsing import parse_obj
from beanie.odm.queries.aggregation import AggregationQuery
from fastapi_pagination import Page
from fastapi_pagination.ext.beanie import apaginate
from common.models.standard_form import StandardForm, Trigger

from backend.app.exceptions import HTTPException
from backend.app.models.enum.FormVersion import FormVersion
from backend.app.schemas.form_versions import FormVersionsDocument
from backend.app.schemas.standard_form import FormDocument
from backend.app.models.dtos.form_actions_dto import FormActionsDto
from backend.app.services.form_concurrency import (
    ensure_not_changed_since,
    form_changed,
    next_updated_at,
)
from backend.app.utils.aggregation_query_builder import create_filter_pipeline
from common.db.routing import write_op


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


# The settings a form is returned with: the workspace association's, plus
# the form's own declared language (``StandardFormSettings.language``), which
# only the form document keeps. Mirrors ``_fold_settings`` in
# repositories/postgres/forms.py.
# When the association has no settings, the language alone: a builder that
# loaded no language would clear it with its first save.
_SETTINGS_WITH_FORM_LANGUAGE = {
    "$cond": [
        {"$eq": [{"$type": "$workspace_form.settings"}, "object"]},
        {"$mergeObjects": ["$workspace_form.settings", {"language": "$settings.language"}]},
        {
            "$cond": [
                {"$eq": [{"$type": "$settings.language"}, "string"]},
                {"language": "$settings.language"},
                "$workspace_form.settings",
            ]
        },
    ]
}


# Arrays the $lookups leave behind once their values are folded into the
# document; nothing reads them and they can be large (every version of a form).
_LOOKUP_SCAFFOLDING = [
    "workspace_form",
    "form",
    "form_groups",
    "versions",
    "responses_deletion_requests",
    "_bc_form_links",
]

# Before ``$unwind: $workspace_form``: how many workspaces the form is linked
# to. A response stored before #768 has no workspace_id and counts for the
# workspace only when that is one (see repositories/response_scope.py).
# Distinct workspaces, not link rows: a duplicated link to the same workspace
# still leaves the form that workspace's only, as the Postgres twin counts it.
_COUNT_FORM_LINKS = {
    "$set": {
        "_bc_form_links": {"$size": {"$setUnion": ["$workspace_form.workspace_id", []]}}
    }
}


def _scoped_lookup(collection: str, workspace_id: PydanticObjectId, alias: str):
    """``$lookup`` of the form's ``collection`` documents (responses or
    deletion requests) that belong to ``workspace_id`` (#768)."""
    return {
        "$lookup": {
            "from": collection,
            "let": {"form_id": "$form_id", "form_links": "$_bc_form_links"},
            "pipeline": [
                {
                    "$match": {
                        "$expr": {
                            "$and": [
                                {"$eq": ["$form_id", "$$form_id"]},
                                {
                                    "$or": [
                                        {"$eq": ["$workspace_id", workspace_id]},
                                        {
                                            "$and": [
                                                {"$eq": ["$$form_links", 1]},
                                                {
                                                    "$eq": [
                                                        {
                                                            "$ifNull": [
                                                                "$workspace_id",
                                                                None,
                                                            ]
                                                        },
                                                        None,
                                                    ]
                                                },
                                            ]
                                        },
                                    ]
                                },
                            ]
                        }
                    }
                },
                {"$project": {"_id": 1, "answers": 1}},
            ],
            "as": alias,
        }
    }


def detach_action(form: FormDocument, action_id: str) -> None:
    """Drop one action from a form's triggers, parameters and secrets, in
    place; every other action keeps its own (the Postgres twin applies it to
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


class FormRepository:
    def _forms_in_workspace_query(
        self,
        workspace_id: PydanticObjectId,
        form_id_list: List[str],
        is_admin: bool,
        sort=None,
    ) -> AggregationQuery:
        aggregation_pipeline = [
            {
                "$lookup": {
                    "from": "workspace_forms",
                    "localField": "form_id",
                    "foreignField": "form_id",
                    "as": "workspace_form",
                }
            },
            _COUNT_FORM_LINKS,
            {"$unwind": "$workspace_form"},
            {"$match": {"workspace_form.workspace_id": workspace_id}},
            {
                "$set": {
                    "settings": _SETTINGS_WITH_FORM_LANGUAGE,
                    "imported_by": "$workspace_form.user_id",
                }
            },
            {
                "$lookup": {
                    "from": "responder_group_form",
                    "localField": "form_id",
                    "foreignField": "form_id",
                    "as": "form_groups",
                }
            },
            {
                "$lookup": {
                    "from": "responder_group",
                    "localField": "form_groups.group_id",
                    "foreignField": "_id",
                    "as": "groups",
                }
            },
        ]

        aggregation_pipeline.extend(create_filter_pipeline(sort=sort))

        if is_admin:
            aggregation_pipeline.extend(
                [
                    _scoped_lookup("form_responses", workspace_id, "responses"),
                    {
                        "$set": {
                            "responses": {
                                "$filter": {
                                    "input": "$responses",
                                    "as": "item",
                                    "cond": {
                                        "$ne": [{"$type": "$$item.answers"}, "missing"]
                                    },
                                }
                            }
                        }
                    },
                    {"$set": {"responses": {"$size": "$responses"}}},
                    _scoped_lookup(
                        "responses_deletion_requests",
                        workspace_id,
                        "responses_deletion_requests",
                    ),
                    {
                        "$set": {
                            "deletion_requests": {
                                "$size": "$responses_deletion_requests"
                            }
                        }
                    },
                    {
                        "$lookup": {
                            "from": "form_versions",
                            "localField": "form_id",
                            "foreignField": "form_id",
                            "as": "versions",
                        }
                    },
                    {"$set": {"is_published": {"$gt": [{"$size": "$versions"}, 0]}}},
                ]
            )
        aggregation_pipeline.append({"$unset": _LOOKUP_SCAFFOLDING})
        return FormDocument.find({"form_id": {"$in": form_id_list}}).aggregate(
            aggregation_pipeline
        )

    async def get_forms_in_workspace(
        self,
        workspace_id: PydanticObjectId,
        form_id_list: List[str],
        is_admin: bool,
        sort=None,
    ) -> List[dict]:
        """Draft forms of a workspace with their workspace settings, importer,
        responder groups and — for admins — response/deletion counts and publish
        state. Raw documents, shaped for ``FormDtoCamelModel``."""
        return await self._forms_in_workspace_query(
            workspace_id, form_id_list, is_admin, sort
        ).to_list()

    async def paginate_forms_in_workspace(
        self,
        workspace_id: PydanticObjectId,
        form_id_list: List[str],
        is_admin: bool,
        sort=None,
    ) -> Page:
        return await apaginate(
            self._forms_in_workspace_query(workspace_id, form_id_list, is_admin, sort)
        )

    def _published_forms_in_workspace_query(
        self,
        workspace_id: PydanticObjectId,
        form_id_list: List[str],
        sort=None,
        get_actions=False,
    ):
        aggregation_pipeline = [
            {"$sort": {"version": -1}},
            {"$group": {"_id": "$form_id", "latestVersion": {"$first": "$$ROOT"}}},
            {"$replaceRoot": {"newRoot": "$latestVersion"}},
            {
                "$lookup": {
                    "from": "workspace_forms",
                    "localField": "form_id",
                    "foreignField": "form_id",
                    "as": "workspace_form",
                }
            },
            _COUNT_FORM_LINKS,
            {"$unwind": "$workspace_form"},
            {"$match": {"workspace_form.workspace_id": workspace_id}},
            {"$set": {"settings": _SETTINGS_WITH_FORM_LANGUAGE, "is_published": True}},
            _scoped_lookup("form_responses", workspace_id, "responses"),
            {
                "$set": {
                    "responses": {
                        "$filter": {
                            "input": "$responses",
                            "as": "item",
                            "cond": {"$ne": [{"$type": "$$item.answers"}, "missing"]},
                        }
                    }
                }
            },
            {"$set": {"responses": {"$size": "$responses"}}},
            _scoped_lookup(
                "responses_deletion_requests",
                workspace_id,
                "responses_deletion_requests",
            ),
            {"$set": {"deletion_requests": {"$size": "$responses_deletion_requests"}}},
        ]
        get_action_aggregation = [
            {
                "$lookup": {
                    "from": "forms",
                    "localField": "form_id",
                    "foreignField": "form_id",
                    "as": "form",
                }
            },
            {"$unwind": "$form"},
            {
                "$set": {
                    "actions": "$form.actions",
                    "parameters": "$form.parameters",
                    "secrets": "$form.secrets",
                }
            },
            {
                "$lookup": {
                    "from": "responder_group_form",
                    "localField": "form_id",
                    "foreignField": "form_id",
                    "as": "form_groups",
                }
            },
            {
                "$lookup": {
                    "from": "responder_group",
                    "localField": "form_groups.group_id",
                    "foreignField": "_id",
                    "as": "groups",
                }
            },
        ]
        if get_actions:
            aggregation_pipeline.extend(get_action_aggregation)
        aggregation_pipeline.extend(create_filter_pipeline(sort=sort))
        aggregation_pipeline.append({"$unset": _LOOKUP_SCAFFOLDING})
        return FormVersionsDocument.find({"form_id": {"$in": form_id_list}}).aggregate(
            aggregation_pipeline=aggregation_pipeline
        )

    async def get_published_forms_in_workspace(
        self,
        workspace_id: PydanticObjectId,
        form_id_list: List[str],
        sort=None,
        get_actions=False,
    ) -> List[dict]:
        """Latest published version of each form, with workspace settings and
        response/deletion counts; ``get_actions`` adds the draft's actions,
        parameters, secrets and responder groups."""
        return await self._published_forms_in_workspace_query(
            workspace_id, form_id_list, sort, get_actions
        ).to_list()

    async def paginate_published_forms_in_workspace(
        self,
        workspace_id: PydanticObjectId,
        form_id_list: List[str],
        sort=None,
        get_actions=False,
    ) -> Page:
        return await apaginate(
            self._published_forms_in_workspace_query(
                workspace_id, form_id_list, sort, get_actions
            )
        )

    async def search_form_in_workspace(
        self,
        workspace_id: PydanticObjectId,
        form_ids: List[str],
        query: str,
        published: bool = False,
    ):
        query_document = FormDocument
        if published:
            query_document = FormVersionsDocument

        aggregation_pipeline = [
            {
                "$lookup": {
                    "from": "workspace_forms",
                    "localField": "form_id",
                    "foreignField": "form_id",
                    "as": "workspace_form",
                }
            },
            {"$unwind": "$workspace_form"},
            {"$match": {"workspace_form.workspace_id": workspace_id}},
            {
                "$set": {
                    "settings": "$workspace_form.settings",
                    "imported_by": "$workspace_form.user_id",
                }
            },
        ]

        if published:
            aggregation_pipeline.extend(
                [
                    {"$sort": {"version": -1}},
                    {
                        "$group": {
                            "_id": "$form_id",
                            "latestVersion": {"$first": "$$ROOT"},
                        }
                    },
                    {"$replaceRoot": {"newRoot": "$latestVersion"}},
                ]
            )
        if not published:
            aggregation_pipeline.extend(
                [
                    {
                        "$lookup": {
                            "from": "form_versions",
                            "localField": "form_id",
                            "foreignField": "form_id",
                            "as": "versions",
                        }
                    },
                    {"$set": {"is_published": {"$gt": [{"$size": "$versions"}, 0]}}},
                ]
            )

        aggregation_pipeline.append({"$sort": {"created_at": -1}})
        aggregation_pipeline.append({"$unset": _LOOKUP_SCAFFOLDING})
        return (
            await query_document.find(
                {
                    "form_id": {"$in": form_ids},
                    "$or": [
                        {"title": {"$regex": query, "$options": "i"}},
                        {"description": {"$regex": query, "$options": "i"}},
                    ],
                }
            )
            .aggregate(aggregation_pipeline=aggregation_pipeline)
            .to_list()
        )

    @write_op
    async def save_form(self, form: FormDocument):
        return await form.save()

    @write_op
    async def save_form_version(
        self, form_version: FormVersionsDocument
    ) -> FormVersionsDocument:
        return await form_version.save()

    @write_op
    async def delete_versions_by_imported_form_id(self, imported_form_id: str):
        return await FormVersionsDocument.find(
            {"imported_form_id": imported_form_id}
        ).delete()

    async def get_forms_by_form_ids(self, form_ids: List[str]) -> List[FormDocument]:
        return await FormDocument.find({"form_id": {"$in": form_ids}}).to_list()

    @write_op
    async def delete_form(self, form_id: str):
        form = await FormDocument.find_one({"form_id": form_id})
        if not form:
            raise HTTPException(status_code=404, content="Form not found")
        return await form.delete()

    @write_op
    async def delete_forms(self, form_ids: List[str]):
        return await FormDocument.find({"form_id": {"$in": form_ids}}).delete()

    @write_op(replay=True)
    async def create_form(self, form: StandardForm) -> FormDocument:
        form_document = FormDocument(**form.model_dump(mode="json"))
        return await form_document.save()

    @write_op
    async def update_form(self, form_id: PydanticObjectId, form: StandardForm):
        form_document = await FormDocument.find_one({"form_id": str(form_id)})
        apply_form_update(form_document, form)
        return await form_document.save()

    async def _stored_draft(self, form_id: PydanticObjectId):
        """The draft as stored (raw BSON), for a conditional write."""
        return await FormDocument.get_pymongo_collection().find_one(
            {"form_id": str(form_id)}
        )

    @write_op(replay=True)
    async def update_form_if_unchanged(
        self,
        form_id: PydanticObjectId,
        form: StandardForm,
        expected_updated_at: datetime,
    ):
        """``update_form`` as a conditional write: refused with 409 when the
        stored draft is newer than ``expected_updated_at``
        (services/form_concurrency.py), including when another save lands
        between this read and this write. The filter is the stored
        ``updated_at`` exactly as read (string or date), so the write applies
        only to the draft that passed the check. Replayed: the mirror stores
        this document, with this ``updated_at``, instead of re-checking."""
        raw = await self._stored_draft(form_id)
        if raw is None:
            return None
        form_document = parse_obj(FormDocument, raw)
        ensure_not_changed_since(form_document.updated_at, expected_updated_at)
        apply_form_update(form_document, form)
        form_document.updated_at = next_updated_at(form_document.updated_at)
        result = await FormDocument.get_pymongo_collection().update_one(
            {"_id": raw["_id"], "updated_at": raw.get("updated_at")},
            {
                "$set": get_dict(
                    form_document,
                    to_db=True,
                    exclude={"_id"},
                    keep_nulls=FormDocument.get_settings().keep_nulls,
                )
            },
        )
        if result.matched_count == 0:
            raise form_changed()
        return form_document

    @write_op
    async def set_form_logo(self, form_id: str, logo: Optional[str]):
        """Set (or, with None, clear) the draft's logo URL, nothing else, so a
        builder autosave running at the same time keeps its own changes."""
        await FormDocument.find_one({"form_id": str(form_id)}).update(
            {"$set": {"logo": logo}}
        )
        return await FormDocument.find_one({"form_id": str(form_id)})

    async def get_form_document_by_id(self, form_id: str):
        return await FormDocument.find_one({"form_id": form_id})

    async def get_latest_version_of_form(self, form_id: PydanticObjectId):
        return (
            await FormVersionsDocument.find({"form_id": str(form_id)})
            .sort(("version", SortDirection.DESCENDING))
            .first_or_none()
        )

    async def get_versions_of_form(self, form_id: PydanticObjectId):
        """Every published version of a form, oldest first."""
        return (
            await FormVersionsDocument.find({"form_id": str(form_id)})
            .sort(("version", SortDirection.ASCENDING))
            .to_list()
        )

    async def get_form_by_by_version(
        self, form_id: PydanticObjectId, version: FormVersion | int
    ):
        if version == FormVersion.latest:
            return await self.get_latest_version_of_form(form_id=form_id)
        # form_id arrives as an ObjectId; the field is stored as its string
        return await FormVersionsDocument.find_one(
            {"form_id": str(form_id), "version": version}
        )

    @write_op(replay=True)
    async def publish_form(self, form: FormDocument, version: int):
        new_form_version = FormVersionsDocument(
            **form.model_dump(mode="json"), version=version
        )
        new_form_version.id = None
        return await new_form_version.save()

    async def get_form_by_id(self, form_id: PydanticObjectId):
        return await FormDocument.find_one({"form_id": str(form_id)})

    @write_op
    async def remove_action_from_all_forms(self, action_id: PydanticObjectId):
        """Detach a deleted action from every form and published version: drop
        it from the triggers and forget its parameters and secrets (moved here
        from the actions repository — it writes forms, so it belongs to the
        forms group).

        Triggers hold ``{id, enabled}`` entries. A form can hold the action's
        credentials before the action is attached (OAuth runs first), so its
        parameters and secrets are removed wherever they are. Targeted
        ``$pull``/``$unset`` updates, each filtered to documents where the path
        exists, so concurrent edits of a form are not overwritten and other
        actions' parameters and secrets are left alone."""
        key = str(action_id)
        for document in (FormDocument, FormVersionsDocument):
            for trigger in Trigger:
                path = f"actions.{trigger.value}"
                await document.find({f"{path}.id": action_id}).update(
                    {"$pull": {path: {"id": action_id}}}
                )
            for bag in ("parameters", "secrets"):
                path = f"{bag}.{key}"
                await document.find({path: {"$exists": True}}).update(
                    {"$unset": {path: ""}}
                )

    @write_op
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
        not other actions. A compare-and-set on the stored list, so concurrent
        calls neither lose a count nor both claim a marker. True when it
        changed something."""
        collection = FormDocument.get_pymongo_collection()
        path = f"parameters.{action_id}"
        for _ in range(5):
            raw = await collection.find_one({"form_id": str(form_id)})
            if raw is None:
                return False
            stored = (raw.get("parameters") or {}).get(str(action_id))
            merged = merge_action_parameters(
                stored, values, increment, only_if_absent, remove
            )
            if merged is None:
                return False
            if not isinstance(raw.get("parameters"), dict):
                # no parameters at all yet (null or missing)
                result = await collection.update_one(
                    {"_id": raw["_id"], "parameters": raw.get("parameters")},
                    {"$set": {"parameters": {str(action_id): merged}}},
                )
            else:
                # null matches a missing list too
                result = await collection.update_one(
                    {"_id": raw["_id"], path: stored}, {"$set": {path: merged}}
                )
            if result.matched_count == 1:
                return True
        return False

    @write_op
    async def replace_action_credential(
        self,
        form_id: str,
        action_id: str,
        credential: str,
        clear_parameters: Optional[List[str]] = None,
    ) -> dict:
        """Store a new credential for one action and drop the named parameters
        (the Sheets re-consent markers) in one write of the draft, a
        compare-and-set like ``update_action_parameters`` (``updated_at`` and
        other actions untouched). Then every published version's copy of the
        action's credential is replaced too, so no stored copy of the old
        ciphertext is left. Returns ``{"stored": bool, "previous": str|None}``:
        the ciphertext the draft held before (``stored`` is False for an
        unknown form)."""
        key = str(action_id)
        collection = FormDocument.get_pymongo_collection()
        stored_ok, previous = False, None
        for _ in range(5):
            raw = await collection.find_one({"form_id": str(form_id)})
            if raw is None:
                return {"stored": False, "previous": None}
            match = {"_id": raw["_id"]}
            changes = {}
            stored_secrets = raw.get("secrets")
            secrets_now = (
                stored_secrets.get(key) if isinstance(stored_secrets, dict) else None
            )
            new_secrets, previous = replace_credential_secret(secrets_now, credential)
            if isinstance(stored_secrets, dict):
                # null matches a missing list too
                match[f"secrets.{key}"] = secrets_now
                changes[f"secrets.{key}"] = new_secrets
            else:
                match["secrets"] = stored_secrets
                changes["secrets"] = {key: new_secrets}
            stored_params = raw.get("parameters")
            params_now = (
                stored_params.get(key) if isinstance(stored_params, dict) else None
            )
            merged = merge_action_parameters(params_now, remove=clear_parameters)
            if merged is not None:
                match[f"parameters.{key}"] = params_now
                changes[f"parameters.{key}"] = merged
            result = await collection.update_one(match, {"$set": changes})
            if result.matched_count == 1:
                stored_ok = True
                break
        if not stored_ok:
            raise RuntimeError("the form changed concurrently; try again")
        versions = FormVersionsDocument.get_pymongo_collection()
        path = f"secrets.{key}"
        async for raw in versions.find(
            {"form_id": str(form_id), f"{path}.name": CREDENTIALS_SECRET},
            {"_id": 1, path: 1},
        ):
            current = (raw.get("secrets") or {}).get(key)
            replaced = replace_version_credentials(current, credential)
            if replaced is not None:
                await versions.update_one(
                    {"_id": raw["_id"], path: current}, {"$set": {path: replaced}}
                )
        return {"stored": True, "previous": previous}

    async def get_forms_with_action_secrets(
        self, action_ids: List[str]
    ) -> List[FormDocument]:
        """Drafts holding secrets for any of ``action_ids``."""
        if not action_ids:
            return []
        return await FormDocument.find(
            {"$or": [{f"secrets.{key}": {"$exists": True}} for key in action_ids]}
        ).to_list()

    @write_op
    async def update_form_actions(
        self,
        form_id: PydanticObjectId,
        action_id: PydanticObjectId,
        form: StandardForm,
        payload: FormActionsDto,
    ):
        # Accessing secrets using the action_id
        secrets = form.secrets[str(action_id)]

        # Update the secret for that action_id
        for secret in secrets:
            if secret.name == payload.name:
                secret.value = payload.value

        form.secrets[str(action_id)] = secrets

        return await form.save()
