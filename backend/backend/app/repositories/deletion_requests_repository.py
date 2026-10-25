from typing import Optional

from fastapi_pagination.ext.beanie import apaginate

from backend.app.models.filter_queries.form_responses import FormResponseFilterQuery
from backend.app.models.filter_queries.sort import SortRequest
from backend.app.repositories.response_scope import (
    ResponseScope,
    form_importers,
    form_titles,
    mongo_lookup_stages,
)
from backend.app.schemas.standard_form_response import FormResponseDeletionRequest
from backend.app.utils.aggregation_query_builder import create_filter_pipeline


class DeletionRequestsRepository:
    def __init__(self, form_repo, workspace_form_repo):
        # the forms group's repositories (see response_scope)
        self._forms = form_repo
        self._workspace_forms = workspace_form_repo

    # TODO Remove duplicate code by extracting the query and aggregation to a function
    async def get_deletion_requests(
        self,
        scope: ResponseScope,
        data_owner_identifier: Optional[str] = None,
        filter_query: FormResponseFilterQuery = None,
        sort: SortRequest = None,
        anonymous_identity: Optional[str] = None,
    ):
        """Deletion requests in ``scope`` (optionally one responder's: by
        their address, or by the anonymous identity hash on requests for
        responses they submitted without it), each carrying its form's title,
        who imported it into the scope's workspace and the response's
        submission uuid."""
        titles = await form_titles(self._forms, scope.form_ids)
        importers = await form_importers(
            self._workspace_forms, titles, scope.workspace_id
        )
        # both $unwinds must match
        titles = {f: t for f, t in titles.items() if f in importers}
        find_query = scope.mongo_filter()
        owner = []
        if data_owner_identifier is not None:
            owner.append({"dataOwnerIdentifier": data_owner_identifier})
        if anonymous_identity is not None:
            owner.append({"anonymous_identity": anonymous_identity})
        if owner:
            # The scope is itself an $or (this workspace, or legacy rows):
            # both must hold, so neither may replace the other.
            find_query = {"$and": [find_query, {"$or": owner}]}
        aggregate_query = [
            *mongo_lookup_stages("form_title", titles),
            # this workspace's link only: a provider form linked to several
            # workspaces has an importer in each (#768)
            *mongo_lookup_stages("form_imported_by", importers),
            # Carry the response's receipt number so a deletion request is
            # cross-referenceable with the submission it covers: the copy in
            # the request's workspace (any copy for a request stored before
            # requests carried one).
            {
                "$lookup": {
                    "from": "form_responses",
                    "localField": "response_id",
                    "foreignField": "response_id",
                    "let": {"workspace_id": {"$ifNull": ["$workspace_id", None]}},
                    "pipeline": [
                        {
                            "$match": {
                                "$expr": {
                                    "$or": [
                                        {"$eq": ["$$workspace_id", None]},
                                        {"$eq": ["$workspace_id", "$$workspace_id"]},
                                    ]
                                }
                            }
                        }
                    ],
                    "as": "response_doc",
                },
            },
            {
                "$set": {
                    "submission_uuid": {
                        "$arrayElemAt": ["$response_doc.submission_uuid", 0]
                    }
                }
            },
            {"$unset": "response_doc"},
        ]

        aggregate_query.extend(
            create_filter_pipeline(filter_object=filter_query, sort=sort)
        )

        deletion_requests_query = FormResponseDeletionRequest.find(
            find_query
        ).aggregate(aggregate_query)
        return await apaginate(deletion_requests_query)
