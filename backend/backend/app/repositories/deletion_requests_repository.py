from typing import Dict, Any

from fastapi_pagination.ext.beanie import paginate

from backend.app.models.filter_queries.form_responses import FormResponseFilterQuery
from backend.app.models.filter_queries.sort import SortRequest
from backend.app.schemas.standard_form_response import FormResponseDeletionRequest
from backend.app.utils.aggregation_query_builder import create_filter_pipeline


class DeletionRequestsRepository:

    # TODO Remove duplicate code by extracting the query and aggregation to a function
    @staticmethod
    async def get_deletion_requests(
        form_ids,
        extra_find_query: Dict[str, Any] = None,
        filter_query: FormResponseFilterQuery = None,
        sort: SortRequest = None,
    ):
        find_query = {"form_id": {"$in": form_ids}}
        if extra_find_query is not None:
            find_query.update(extra_find_query)
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
        ]

        aggregate_query.extend(
            create_filter_pipeline(filter_object=filter_query, sort=sort)
        )

        deletion_requests_query = FormResponseDeletionRequest.find(
            find_query
        ).aggregate(aggregate_query)
        return await paginate(deletion_requests_query)
