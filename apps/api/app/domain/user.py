# 文件说明：领域对象：user。
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

UserRole = Literal["user", "admin"]


@dataclass(frozen=True, slots=True)
class User:
    id: UUID
    email: str
    password_hash: str
    display_name: str
    default_origin: str | None
    currency: str
    language: str
    role: UserRole
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ProfileChanges:
    display_name: str | None = None
    default_origin: str | None = None
    clear_default_origin: bool = False
    currency: str | None = None
    language: str | None = None
