from camel_converter import to_camel, to_snake

from backend.app.models.filter_queries.sort import SortRequest, SortOrder


def create_filter_pipeline(filter_object=None, sort: SortRequest = None):
    pipeline = []
    if filter_object:
        matching_dict = filter_object.dict(exclude_unset=True, exclude_none=True)
        if matching_dict:
            all_matchers = []
            for k, v in matching_dict.items():
                all_matchers.append(
                    {
                        "$or": [
                            {to_camel(k): {"$regex": v, "$options": "i"}},
                            {to_snake(k): {"$regex": v, "$options": "i"}},
                        ]
                    }
                )
            pipeline.append({"$match": {"$and": all_matchers}})
    if sort and sort.sort_by:
        sort_order = 1 if sort.sort_order == SortOrder.ASCENDING else -1
        pipeline.append({"$sort": {sort.sort_by: sort_order}})
    return pipeline
