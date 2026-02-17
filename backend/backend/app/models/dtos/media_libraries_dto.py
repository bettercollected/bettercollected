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
    media_type: Optional[MediaType] = None
    media_name: Optional[str] = None


class MediaLibraryDto(BaseModel):
    media_id: Optional[PydanticObjectId] = None
    workspace_id: Optional[str] = None
    media_url: Optional[str] = None
    media_type: Optional[MediaType] = None
    media_name: Optional[str] = None


class MediaLibraryCamelModel(CamelModel, MediaLibraryDto):
    pass


class MediaLibrary(MediaLibraryDto):
    s3_key: Optional[str] = None
    pass
