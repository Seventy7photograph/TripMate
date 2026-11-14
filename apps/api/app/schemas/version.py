# 文件说明：Pydantic 数据契约：version。
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TripVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    version: int
    snapshot: dict[str, object]
    created_by: UUID
    created_at: datetime


class TripVersionHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    trip_id: UUID
    current_version: int
    versions: list[TripVersionResponse]


class RestoreVersionRequest(BaseModel):
    expected_version: int = Field(ge=1)
