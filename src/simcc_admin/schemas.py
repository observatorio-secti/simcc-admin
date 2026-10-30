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
        total_pages = (total_items + per_page - 1) // per_page if per_page > 0 else 0
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
    collection_id: UUID | None = None


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


class InstitutionRef(BaseModel):
    id: UUID
    name: str
    acronym: str
    model_config = ConfigDict(from_attributes=True)


class InstitutionCreate(BaseModel):
    name: str
    acronym: str


class InstitutionUpdate(BaseModel):
    name: str
    acronym: str


class InstitutionPublic(InstitutionRef):
    created_at: datetime


class Affiliation(BaseModel):
    institution: InstitutionRef
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# --- Schemas de Coleções ---


class CollectionRef(BaseModel):
    id: UUID
    slug: str
    name: str
    model_config = ConfigDict(from_attributes=True)


class CollectionCreate(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")
    name: str = Field(min_length=1)
    description: str | None = None
    refresh_interval_days: int = Field(default=1, ge=1)


class CollectionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1)
    description: str | None = None
    refresh_interval_days: int | None = Field(default=None, ge=1)
    is_default: bool | None = None


class CollectionPublic(CollectionRef):
    description: str | None = None
    refresh_interval_days: int
    is_default: bool
    created_at: datetime
    researcher_count: int = 0


class CollectionMembership(BaseModel):
    collection: CollectionRef
    attributes: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ResearcherCreate(BaseModel):
    name: str
    lattes_id: str
    institution_ids: list[UUID] = Field(default_factory=list)
    collection_ids: list[UUID] = Field(default_factory=list)


class ResearcherUpdate(BaseModel):
    name: str
    lattes_id: str


class ResearcherItem(BaseModel):
    researcher_id: UUID
    name: str
    lattes_id: str
    created_at: datetime
    affiliations: list[Affiliation] = Field(default_factory=list)
    collections: list[CollectionMembership] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


class ResearcherDetail(ResearcherItem):
    pass


class ResearcherSearchResponse(BaseModel):
    data: list[ResearcherItem]
    pagination: Pagination
    filters_applied: FiltersApplied
    sort: Sort
    meta: Meta
    facets: dict[str, Any] | None = None
    summary: dict[str, Any] | None = None


from simcc_admin.models import UserRole

# --- Schemas de Usuários (com UUID) ---


class UserSchema(BaseModel):
    username: str
    email: EmailStr
    password: str


class UserPublic(BaseModel):
    id: UUID
    username: str
    email: EmailStr | None = None
    role: UserRole = UserRole.DEFAULT
    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str
