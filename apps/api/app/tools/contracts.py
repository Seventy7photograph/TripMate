# 文件说明：Agent 受控工具：contracts。
from collections.abc import Awaitable, Callable
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.tools.context import ToolContext

ToolRisk = Literal["read", "write"]


class ToolSpec(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    name: str = Field(min_length=1, max_length=80, pattern=r"^[a-z][a-z0-9_]*$")
    description: str = Field(min_length=1, max_length=500)
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    provider_type: str = Field(min_length=1, max_length=40)
    risk: ToolRisk = "read"
    timeout_seconds: float = Field(default=30.0, gt=0.0, le=300.0)
    max_retries: int = Field(default=1, ge=0, le=3)


ToolHandler = Callable[[ToolContext, BaseModel], Awaitable[BaseModel]]
