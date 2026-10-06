from typing import Optional

from fastapi_pagination.ext.beanie import apaginate

from backend.app.models.filter_queries.form_responses import FormResponseFilterQuery
from backend.app.models.filter_queries.sort import SortRequest
from backend.app.repositories.response_scope import ResponseScope
from backend.app.schemas.standard_form_response import FormResponseDeletionRequest
from backend.app.utils.aggregation_query_builder import create_filter_pipeline


class DeletionRequestsRepository:

    # TODO Remove duplicate code by extracting the query and aggregation to a function
    @staticmethod
    async def get_deletion_requests(
        scope: ResponseScope,
        data_owner_identifier: Optional[str] = None,
        filter_query: FormResponseFilterQuery = None,
        sort: SortRequest = None,
    ):
        """Deletion requests in ``scope`` (optionally one responder's), each
        carrying its form's title, who imported it into the scope's workspace
        and the response's submission uuid."""
        find_query = scope.mongo_filter()
        if data_owner_identifier is not None:
            find_query["dataOwnerIdentifier"] = data_owner_identifier
        aggregate_query = [
            {
                "$lookup": {
                    "from": "forms",
                    "localField": "form_id",
                    "foreignField": "form_id",
                    "as": "form",
                },
            },
            {"$set": {"form_title": "$form.title"}},
            {"$unwind": "$form_title"},
            {
                # this workspace's link only: a provider form linked to
                # several workspaces has an importer in each (#768)
                "$lookup": {
                    "from": "workspace_forms",
                    "let": {"form_id": "$form_id"},
                    "pipeline": [
                        {
                            "$match": {
                                "$expr": {
                                    "$and": [
                                        {"$eq": ["$form_id", "$$form_id"]},
                                        {"$eq": ["$workspace_id", scope.workspace_id]},
                                    ]
                                }
                            }
                        }
                    ],
                    "as": "workspace_form",
                },
            },
            {"$set": {"form_imported_by": "$workspace_form.user_id"}},
            {"$unwind": "$form_imported_by"},
            # Carry the response's receipt number so a deletion request is
            # cross-referenceable with the submission it covers.
            {
                "$lookup": {
                    "from": "form_responses",
                    "localField": "response_id",
                    "foreignField": "response_id",
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
            {"$unset": ["response_doc", "form", "workspace_form"]},
        ]

        aggregate_query.extend(
            create_filter_pipeline(filter_object=filter_query, sort=sort)
        )

        deletion_requests_query = FormResponseDeletionRequest.find(
            find_query
        ).aggregate(aggregate_query)
        return await apaginate(deletion_requests_query)
