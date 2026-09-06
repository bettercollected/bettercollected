"""The three Beanie documents here have no ``Settings.name``, so their Mongo
collections are literally named after the classes; the tables get sane names
and record the collection they mirror."""

from __future__ import annotations

from sqlalchemy import Index

from common.db import BaseRow, MirrorWriteFailureMixin
from googleform.db.base import S, Base


class GoogleFormRow(Base, BaseRow):
    __tablename__ = "google_forms"
    __mongo_collection__ = "GoogleFormDocument"
    google_form_id = S.text("formId", name="google_form_id")
    provider = S.text("provider")
    __table_args__ = (Index(None, "google_form_id"),)


class GoogleFormResponseRow(Base, BaseRow):
    __tablename__ = "google_form_responses"
    __mongo_collection__ = "GoogleFormResponseDocument"
    google_form_id = S.text("formId", name="google_form_id")
    google_response_id = S.text("responseId", name="google_response_id")
    provider = S.text("provider")
    __table_args__ = (
        Index(
            "ix_google_form_responses_form_response",
            "google_form_id",
            "google_response_id",
        ),
    )


class OAuthCredentialRow(Base, BaseRow):
    __tablename__ = "oauth_credentials"
    __mongo_collection__ = "Oauth2CredentialDocument"
    email = S.text("email")
    user_id = S.text("user_id")
    provider = S.text("provider")
    state = S.text("state")
    __table_args__ = (Index(None, "email"), Index(None, "user_id"))


class MirrorWriteFailure(Base, MirrorWriteFailureMixin):
    __tablename__ = "mirror_write_failures"
