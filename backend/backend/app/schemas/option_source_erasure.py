"""One answer of another form that was erased and was offered as an option
(``services/option_sources/erasure.py``): which source question and which
option ids (keyed hashes of the answer, never the text). Written in the same
transaction as the erasure, removed once the choices other people made from
it are redacted. Holds no answer and no name."""

from typing import List

from common.records import Record, RecordId


class OptionSourceErasureDocument(Record):
    workspace_id: RecordId
    # the form whose response was erased, and its question
    form_id: str
    question_id: str
    option_ids: List[str] = []

    class Settings:
        name = "option_source_erasures"
