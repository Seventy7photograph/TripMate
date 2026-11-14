# 文件说明：Prompt 目录 Schema 与版本引用。
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

_SEGMENT_PATTERN = r"^[a-z][a-z0-9-]*$"
_VERSION_PATTERN = r"^\d+\.\d+\.\d+$"


class PromptReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    agent: str = Field(pattern=_SEGMENT_PATTERN)
    prompt_id: str = Field(pattern=_SEGMENT_PATTERN)
    version: str = Field(pattern=_VERSION_PATTERN)


class PromptMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: int = Field(ge=1, le=1)
    agent: str = Field(pattern=_SEGMENT_PATTERN)
    prompt_id: str = Field(pattern=_SEGMENT_PATTERN)
    version: str = Field(pattern=_VERSION_PATTERN)
    description: str = Field(min_length=1, max_length=500)


@dataclass(frozen=True, slots=True)
class LoadedPrompt:
    agent: str
    prompt_id: str
    version: str
    description: str
    content: str
    sha256: str

    def audit_record(self) -> dict[str, str]:
        return {
            "agent": self.agent,
            "prompt_id": self.prompt_id,
            "version": self.version,
            "sha256": self.sha256,
        }
