# 文件说明：Pydantic 数据契约：upload。
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class UploadedAssetResponse(BaseModel):
    id: UUID
    name: str
    mime_type: str
    kind: Literal["image", "document"]
    size_bytes: int
    created_at: datetime
    expires_at: datetime
