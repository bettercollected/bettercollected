from backend.app.models.FilterQueries.sort import SortRequest, SortOrder


def create_filter_pipeline(filter_object=None, sort: SortRequest = None):
    pipeline = []
    if filter_object:
        pipeline.append({"$match": filter_object.dict(exclude_unset=True)})
    if sort and sort.sort_by:
        sort_order = 1 if sort.sort_order == SortOrder.ASCENDING else -1
        pipeline.append({"$sort": {sort.sort_by: sort_order}})
    return pipeline
