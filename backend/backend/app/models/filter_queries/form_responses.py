from typing import Optional

from backend.app.models.filter_queries.base_filter_query import BaseFilterQuery


class FormResponseFilterQuery(BaseFilterQuery):
    data_owner_identifier: Optional[str] = None
    email: Optional[str] = None
