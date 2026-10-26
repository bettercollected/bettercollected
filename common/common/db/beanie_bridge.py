"""Test support: the 4.0 codec, Beanie ``Document`` <-> Postgres row values.

Until 4.1 a Postgres repository accepted and returned Beanie ``Document``
classes and this module was the only place that knew how a document becomes a
row (and back):

* :func:`to_bson_dict` encodes exactly as ``Document.save()`` did - through
  Beanie's ``Encoder`` with the document's own ``bson_encoders`` - so the
  ``doc`` a Postgres row stores is byte-for-byte what Mongo stored, and
  :func:`common.db.canonical.document_checksum` agrees across both stores.
* :func:`row_values` produces the column values for an upsert.
* :func:`from_row_doc` rebuilds the document from a row's ``doc``.

The application no longer uses Beanie: its records are plain pydantic models
(:mod:`common.records`) and :mod:`common.records.codec` replaced this module.
It stays, with Beanie as a test-only dependency, so that the golden fixtures
(:mod:`common.db.codec_golden`) keep proving the record codec writes what the
4.0 codec wrote, and so that the import tests can seed a Mongo exactly as 4.0
did with the frozen original classes. Nothing under ``common`` imports it
at module level.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from datetime import datetime as dt
from datetime import timezone
from typing import (
    AbstractSet,
    Any,
    Dict,
    Generator,
    List,
    Mapping,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
)

from beanie import Document, PydanticObjectId, View, WriteRules, init_beanie
from beanie.odm.documents import DocType
from beanie.odm.utils.encoder import Encoder
from beanie.odm.utils.init import Initializer
from pymongo import AsyncMongoClient
from pymongo.client_session import ClientSession
from pymongo.collection import Collection

from common.clock import utcnow
from common.exceptions import NotFoundError

from common.db.base import SOURCE_APP
from common.db.canonical import canonical_document, checksum, from_canonical_document

D = TypeVar("D", bound=Document)

IntStr = Union[int, str]
AbstractSetIntStr = AbstractSet[IntStr]
MappingIntStrAny = Mapping[IntStr, Any]
TupleGenerator = Generator[Tuple[str, Any], None, None]


class MongoDocument(Document):
    """The 4.0 base class of every stored document (frozen): a Beanie
    ``Document`` with the timestamps and the lookup helpers the 4.0 code used."""

    created_at: Optional[dt] = None
    updated_at: Optional[dt] = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # utcnow(): within a routed write both stores stamp the same instant
        now = utcnow()
        self.created_at = self.created_at if self.created_at else now
        self.updated_at = self.updated_at if self.updated_at else now

    @classmethod
    def pretty_class_name(cls) -> str:
        """
        Returns the pretty class name of the MongoDocument instance.

        The pretty class name is the original class name with the capitalized letters separated by a space.
        Args:
            cls: The class object of the MongoDocument instance.
        Returns:
            The pretty class name of the MongoDocument instance.
        """
        return re.sub(r"([a-z])([A-Z])", r"\1 \2", cls.__name__).lower()

    @classmethod
    def verify_doc_exists(cls, doc, *args) -> DocType:
        """
        Verifies that the given document exists.

        Args:
            doc: The document to be verified.
            *args: Additional arguments that are used to identify the document.
        Returns:
            The document if it exists.
        Raises:
            NotFoundError: If the document does not exist.
        """
        if doc is None:
            raise NotFoundError(
                f"Error {cls.pretty_class_name()} with {args} does not exist."
            )
        return doc

    @classmethod
    async def get(
        cls: Type[DocType],
        document_id: PydanticObjectId,
        session: Optional[ClientSession] = None,
        ignore_cache: bool = False,
        fetch_links: bool = False,
        with_children: bool = False,
        **pymongo_kwargs,
    ) -> Optional["DocType"]:
        """
        Asynchronously gets a single document by its ID.

        Args:
            document_id: The ID of the document to be retrieved.
            session (optional): An asyncio session to be used for the operation.
            ignore_cache (bool): Whether to ignore any previously cached data
                                and retrieve the document directly from the database.
            fetch_links (bool): Whether to include linked documents in the returned data.
            with_children (bool): Whether to include child documents in the returned data.
            **pymongo_kwargs: Additional keyword arguments to be passed to the pymongo library.
        Returns:
            The document with the given ID, if it exists.
            None if the document does not exist or an error occurred.
        """
        doc = await super().get(
            document_id,
            session=session,
            ignore_cache=ignore_cache,
            fetch_links=fetch_links,
            with_children=with_children,
            **pymongo_kwargs,
        )
        return cls.verify_doc_exists(doc, {"id": document_id})

    @classmethod
    def get_sync(cls: Type[DocType], document_id: PydanticObjectId) -> DocType:
        """
        Synchronously gets a single document by its ID.

        Args:
            document_id: The ID of the document to be retrieved.
        Returns:
            The document with the given ID.
        Raises:
            NotFoundError: If the document does not exist.
        """
        collection: Collection = cls.get_pymongo_collection()
        documents = collection.find({"_id": document_id})
        if not documents.count():
            raise NotFoundError(
                f"Error {cls.pretty_class_name()} with {document_id} does not exist."
            )
        return cls(**documents[0])

    @classmethod
    def find_sync(cls: Type[DocType], find_by: Dict[str, Any]) -> List[DocType]:
        """
        Synchronously finds multiple documents by the specified criteria.

        Args:
            find_by: The criteria to use for finding the documents.
        Returns:
            A list of documents matching the given criteria.
        """
        collection: Collection = cls.get_pymongo_collection()
        documents = collection.find(find_by)
        return [cls(**document) for document in documents]

    @classmethod
    async def find_one_by_args(
        cls: Type[DocType],
        *args: Union[Mapping[str, Any], bool],
        projection_model: None = None,
        session: Optional[ClientSession] = None,
        ignore_cache: bool = False,
        fetch_links: bool = False,
    ) -> DocType:
        """
        Asynchronously finds a single document by the specified criteria.

        Args:
            *args: The criteria to use for finding the document.
            projection_model (optional): A model to use for projecting the returned data.
            session (optional): An asyncio session to be used for the operation.
            ignore_cache (bool): Whether to ignore any previously cached data
                                and retrieve the document directly from the database.
            fetch_links (bool): Whether to include linked documents in the returned data.
        Returns:
            The document matching the given criteria.
        Raises:
            NotFoundError: If no document matches the given criteria.
        """
        doc = await super().find_one(
            *args,
            projection_model=projection_model,
            session=session,
            ignore_cache=ignore_cache,
            fetch_links=fetch_links,
        )
        return cls.verify_doc_exists(doc, *args)

    def _iter(
        self,
        to_dict: bool = False,
        by_alias: bool = False,
        include: Union["AbstractSetIntStr", "MappingIntStrAny"] = None,
        exclude: Union["AbstractSetIntStr", "MappingIntStrAny"] = None,
        exclude_unset: bool = True,
        exclude_defaults: bool = False,
        exclude_none: bool = True,
    ) -> "TupleGenerator":
        """
        Iterates over the fields and their values of the document.
        This function allows for the exclusion of certain field values during iteration.

        Args:
            to_dict (bool): Whether to return the fields and values as a dictionary.
            by_alias (bool): Whether to use field aliases as keys in the returned dictionary.
            include (optional): An iterable of field names or aliases to include in the iteration.
            exclude (optional): An iterable of field names or aliases to exclude from the iteration.
            exclude_unset (bool): Whether to exclude fields that have not been set.
            exclude_defaults (bool): Whether to exclude fields with default values.
            exclude_none (bool): Whether to exclude fields with a value of None.
        Returns:
            A generator that yields the field-value pairs of the document.
        """
        return super()._iter(
            to_dict=to_dict,
            by_alias=by_alias,
            include=include,
            exclude=exclude,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
        )

    async def save(
        self,
        session: Optional[ClientSession] = None,
        link_rule: WriteRules = WriteRules.DO_NOTHING,
        **kwargs,
    ) -> DocType:
        self.updated_at = utcnow()
        return await super().save(session, link_rule, **kwargs)



def ensure_id(document: Document) -> Document:
    """Beanie assigns ``_id`` client-side on insert; do the same before an upsert."""
    if document.id is None:
        document.id = PydanticObjectId()
    return document


def derived_object_id(*parts: Any) -> PydanticObjectId:
    """An ObjectId that is a function of ``parts`` — for documents whose identity
    *is* a relation (a group member, a group↔form link). Two stores executing
    the same write then produce the same row, so the mirror needs no replay."""
    digest = hashlib.sha1("\x00".join(str(p) for p in parts).encode()).digest()
    return PydanticObjectId(digest[:12])


def to_bson_dict(document: Document) -> dict[str, Any]:
    encoders = type(document).get_settings().bson_encoders
    return Encoder(custom_encoders=encoders).encode(document)


def _timestamp(value: Any) -> Optional[datetime]:
    """created_at/updated_at as stored: a datetime, or the ISO string bson_encoders produce."""
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def row_values(document: Document, *, source: str = SOURCE_APP) -> dict[str, Any]:
    """Column values for upserting ``document`` into its table."""
    ensure_id(document)
    bson = to_bson_dict(document)
    doc = canonical_document(bson)
    now = datetime.now(timezone.utc)
    return {
        "id": str(document.id),
        "doc": doc,
        "created_at": _timestamp(bson.get("created_at")) or now,
        "updated_at": _timestamp(bson.get("updated_at")) or now,
        "bc_source": source,
        "bc_checksum": checksum(doc),
    }


def from_row_doc(document_cls: Type[D], doc: Mapping[str, Any]) -> D:
    return document_cls.model_validate(from_canonical_document(doc))


# -- Beanie set-up for the tests ---------------------------------------------------

#: Where a client that never connects points (".invalid" never resolves).
NOT_USED_URI = "mongodb://mongo-not-used.invalid:27017/"
#: The server major version Beanie is told without asking one.
ASSUMED_MAJOR_VERSION = 7


def offline_client() -> AsyncMongoClient:
    """A client that never connects (pymongo's async client connects on first
    use): Beanie can set its classes up on it without a server."""
    return AsyncMongoClient(NOT_USED_URI, serverSelectionTimeoutMS=1000)


class _OfflineInitializer(Initializer):
    """Beanie's initialiser without its server round trip: the collection list
    and server version it caches are only consulted for time-series
    collections and views, which none of the tests' classes declare."""

    async def _load_cached_info(self) -> None:
        self._database_major_version = ASSUMED_MAJOR_VERSION
        self._existing_collections = []


async def init_documents(database: Any, document_models, *, required: bool) -> None:
    """``init_beanie`` when ``required`` (a Mongo server answers); otherwise the
    same class set-up with no request to a server (no ``buildInfo``, no
    indexes)."""
    if required:
        await init_beanie(database=database, document_models=list(document_models))
        return
    views = [m for m in document_models if isinstance(m, type) and issubclass(m, View)]
    if views:  # a view is (re)created on the server: it needs Mongo
        raise TypeError(f"views need a Mongo server: {[v.__name__ for v in views]}")
    await _OfflineInitializer(
        database=database, document_models=list(document_models), skip_indexes=True
    )
