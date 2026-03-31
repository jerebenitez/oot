from typing import Literal, List
from pydantic import BaseModel, ConfigDict


class FileMetadata(BaseModel):
    model_config = ConfigDict(strict=True)

    path: str
    base_blob: str | None = None
    status: Literal["new", "modified"]


class Metadata(BaseModel):
    model_config = ConfigDict(strict=True)

    base_blob: str
    files: List[FileMetadata]
