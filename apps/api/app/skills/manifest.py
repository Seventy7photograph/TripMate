# 文件说明：Skill 运行时：manifest。
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SkillStatus = Literal["active", "disabled"]


class SkillManifestError(Exception):
    pass


def _default_schema() -> dict[str, object]:
    return {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    }


class SkillManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1, max_length=80, pattern=r"^[a-z][a-z0-9-]*$")
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    status: SkillStatus = "active"
    description: str = Field(min_length=1, max_length=500)
    input_schema: dict[str, object] = Field(default_factory=_default_schema)
    output_schema: dict[str, object] = Field(default_factory=_default_schema)
    allowed_tools: list[str] = Field(default_factory=list, max_length=12)
    allowed_mcp_connectors: list[str] = Field(default_factory=list, max_length=8)
    max_tool_calls: int = Field(default=8, ge=0, le=8)
    timeout_seconds: float = Field(default=40.0, gt=0, le=120)
    max_tokens: int = Field(default=4_000, ge=1, le=32_000)
    requires_evidence: bool = False
    fallback: str = Field(default="existing_itinerary_graph", min_length=1, max_length=80)

    @field_validator("allowed_tools", "allowed_mcp_connectors")
    @classmethod
    def unique_identifiers(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("identifiers must be unique")
        return values

    @field_validator("input_schema", "output_schema")
    @classmethod
    def schema_must_describe_object(
        cls,
        value: dict[str, object],
    ) -> dict[str, object]:
        if value.get("type") != "object":
            raise ValueError("schema type must be object")
        if value.get("additionalProperties") is not False:
            raise ValueError("schema must set additionalProperties to false")
        return value
