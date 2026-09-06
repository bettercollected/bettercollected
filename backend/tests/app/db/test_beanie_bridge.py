import datetime as dt

from bson import ObjectId

from backend.app.schemas.allowed_origin import AllowedOriginsDocument
from backend.app.schemas.standard_form_response import FormResponseDocument
from common.db import document_checksum, from_row_doc, row_values, to_bson_dict


async def test_row_values_mirror_what_beanie_would_store(_initialized_app):
    doc = AllowedOriginsDocument(origin="https://x.example")
    assert doc.id is None
    values = row_values(doc)
    assert doc.id is not None and values["id"] == str(
        doc.id
    )  # id assigned client-side, like Beanie
    assert values["doc"]["_id"] == {"$oid": str(doc.id)}
    assert values["doc"]["origin"] == "https://x.example"
    assert values["bc_source"] == "app"
    assert values["bc_checksum"] == document_checksum(to_bson_dict(doc))
    assert values["created_at"].tzinfo is not None


async def test_iso_string_timestamps_from_bson_encoders_become_aware_datetimes(
    _initialized_app,
):
    when = dt.datetime(2026, 1, 1, 12, 0, 0, tzinfo=dt.timezone.utc)
    doc = FormResponseDocument(
        form_id="f", response_id="r", created_at=when, updated_at=when
    )
    doc.id = ObjectId()
    bson = to_bson_dict(doc)
    assert isinstance(bson["created_at"], str)  # the bson_encoders quirk
    values = row_values(doc)
    assert values["created_at"] == when and values["updated_at"] == when


async def test_from_row_doc_round_trips_the_document(_initialized_app):
    when = dt.datetime(2026, 1, 1, 12, 0, 0, tzinfo=dt.timezone.utc)
    doc = FormResponseDocument(form_id="f", response_id="r", created_at=when)
    doc.id = ObjectId()
    back = from_row_doc(FormResponseDocument, row_values(doc)["doc"])
    assert back.id == doc.id and back.form_id == "f" and back.created_at == when
    assert document_checksum(to_bson_dict(back)) == document_checksum(to_bson_dict(doc))
