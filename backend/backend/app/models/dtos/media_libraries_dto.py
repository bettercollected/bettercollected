import enum
from fileinput import filename
from typing import Optional
from beanie import PydanticObjectId
from fastapi import UploadFile
from pydantic import BaseModel
from fastapi_camelcase import CamelModel


class MediaType(str, enum.Enum):
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"


class MediaLibraryRequestDto(CamelModel):
    file: UploadFile
    media_type: Optional[MediaType]
    media_name: Optional[str]


class MediaLibraryDto(BaseModel):
    media_id: Optional[PydanticObjectId]
    workspace_id: Optional[str]
    media_url: Optional[str]
    media_type: Optional[MediaType]
    media_name: Optional[str]


class MediaLibraryCamelModel(CamelModel, MediaLibraryDto):
    pass


class MediaLibrary(MediaLibraryDto):
    s3_key: Optional[str]
    pass
