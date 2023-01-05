import re
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
    Union,
)

from beanie import Document, PydanticObjectId
from beanie.odm.documents import DocType
from pymongo.client_session import ClientSession
from pymongo.collection import Collection

from exceptions import NotFoundError

IntStr = Union[int, str]
AbstractSetIntStr = AbstractSet[IntStr]
MappingIntStrAny = Mapping[IntStr, Any]
TupleGenerator = Generator[Tuple[str, Any], None, None]


class MongoDocument(Document):
    """
    Base class for representing a MongoDB document.
    This class defines common methods and attributes for interacting with MongoDB documents.
    """

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
            ignore_cache (bool): Whether to ignore any previously cached data and retrieve the document directly from the database.
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
        collection: Collection = cls.get_motor_collection().delegate
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
        collection: Collection = cls.get_motor_collection().delegate
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
            ignore_cache (bool): Whether to ignore any previously cached data and retrieve the document directly from the database.
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
        exclude_unset: bool = False,
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
