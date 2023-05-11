from typing import Optional

from backend.app.models.filter_queries.base_filter_query import BaseFilterQuery


class FormsFilterQuery(BaseFilterQuery):
    form_id: Optional[str]
