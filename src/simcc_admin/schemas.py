from datetime import datetime
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class Message(BaseModel):
    message: str


# --- Blocos do Envelope Padronizado ---


class Pagination(BaseModel):
    page: int
    per_page: int
    total_items: int
    total_pages: int
    has_next: bool
    has_prev: bool

    @classmethod
    def create(cls, page: int, per_page: int, total_items: int) -> Pagination:
        total_pages = (total_items + per_page - 1) // per_page if per_page > 0 else 1
        return cls(
            page=page,
            per_page=per_page,
            total_items=total_items,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1,
        )


class FiltersApplied(BaseModel):
    q: str | None = None
    institution_id: UUID | None = None


class Sort(BaseModel):
    by: str = "name"
    order: str = "asc"


class Meta(BaseModel):
    took_ms: int = 0
    cached: bool = False
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(tz=ZoneInfo("UTC"))
    )


class GenericEnvelope[T](BaseModel):
    data: list[T]
    pagination: Pagination
    filters_applied: dict[str, Any] = Field(default_factory=dict)
    sort: Sort = Field(default_factory=Sort)
    meta: Meta = Field(default_factory=Meta)
    facets: dict[str, Any] | None = None
    summary: dict[str, Any] | None = None


# --- Schemas do Domínio Acadêmico ---


class InstitutionPublic(BaseModel):
    id: UUID
    name: str
    acronym: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ResearcherItem(BaseModel):
    researcher_id: UUID
    name: str
    lattes_id: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ResearcherSearchResponse(BaseModel):
    data: list[ResearcherItem]
    pagination: Pagination
    filters_applied: FiltersApplied
    sort: Sort
    meta: Meta
    facets: dict[str, Any] | None = None
    summary: dict[str, Any] | None = None


# --- Schemas de Usuários (com UUID) ---


class UserSchema(BaseModel):
    username: str
    email: EmailStr
    password: str


class UserPublic(BaseModel):
    id: UUID
    username: str
    email: EmailStr | None = None
    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str
