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
    @classmethod
    def pretty_class_name(cls) -> str:
        return re.sub(r"([a-z])([A-Z])", r"\1 \2", cls.__name__).lower()

    @classmethod
    def verify_doc_exists(cls, doc, *args) -> DocType:
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
        doc = await super().get(
            document_id,
            session=session,
            ignore_cache=ignore_cache,
            fetch_links=fetch_links,
            with_children=with_children,
            **pymongo_kwargs,
        )
        return cls.verify_doc_exists(doc, {"id": document_id})

    # Get method for a single document by id synchronously
    @classmethod
    def get_sync(cls: Type[DocType], document_id: PydanticObjectId) -> DocType:
        collection: Collection = cls.get_motor_collection().delegate
        documents = collection.find({"_id": document_id})
        if not documents.count():
            raise NotFoundError(
                f"Error {cls.pretty_class_name()} with {document_id} does not exist."
            )
        return cls(**documents[0])

    # Find method for finding documents
    @classmethod
    def find_sync(cls: Type[DocType], find_by: Dict[str, Any]) -> List[DocType]:
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
        doc = await super().find_one(
            *args,
            projection_model=projection_model,
            session=session,
            ignore_cache=ignore_cache,
            fetch_links=fetch_links,
        )
        return cls.verify_doc_exists(doc, *args)

    # Override iter function to exclude the values that are set None
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
        return super()._iter(
            to_dict=to_dict,
            by_alias=by_alias,
            include=include,
            exclude=exclude,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
        )
