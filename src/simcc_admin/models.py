from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import ClassVar
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import (
    Mapped,
    mapped_as_dataclass,
    mapped_column,
    registry,
    relationship,
)

table_registry = registry()


class UserRole(str, Enum):
    DEFAULT = "DEFAULT"
    ADMIN = "ADMIN"


# --- Schema Academic ---


@mapped_as_dataclass(table_registry)
class Institution:
    __tablename__ = "institutions"
    __table_args__: ClassVar = {"schema": "academic"}

    id: Mapped[UUID] = mapped_column(
        init=False,
        primary_key=True,
        default_factory=uuid4,
        server_default=func.gen_random_uuid(),
    )
    name: Mapped[str] = mapped_column(unique=True)
    acronym: Mapped[str] = mapped_column(unique=True)
    created_at: Mapped[datetime] = mapped_column(init=False, server_default=func.now())
    researchers: Mapped[list[ResearcherInstitution]] = relationship(
        init=False,
        back_populates="institution",
        cascade="all, delete-orphan",
        default_factory=list,
    )


@mapped_as_dataclass(table_registry)
class Collection:
    __tablename__ = "collections"
    __table_args__ = (
        CheckConstraint(
            "refresh_interval_days >= 1",
            name="ck_academic_collections_refresh_interval",
        ),
        Index(
            "uq_academic_collections_default",
            "is_default",
            unique=True,
            postgresql_where=text("is_default"),
        ),
        {"schema": "academic"},
    )

    id: Mapped[UUID] = mapped_column(
        init=False,
        primary_key=True,
        default_factory=uuid4,
        server_default=func.gen_random_uuid(),
    )
    slug: Mapped[str] = mapped_column(unique=True, index=True)
    name: Mapped[str] = mapped_column(unique=True)
    description: Mapped[str | None] = mapped_column(nullable=True, default=None)
    refresh_interval_days: Mapped[int] = mapped_column(
        default=1, server_default="1"
    )
    is_default: Mapped[bool] = mapped_column(
        default=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(
        init=False, server_default=func.now()
    )
    researchers: Mapped[list[ResearcherCollection]] = relationship(
        init=False,
        back_populates="collection",
        default_factory=list,
    )


@mapped_as_dataclass(table_registry)
class Researcher:
    __tablename__ = "researchers"
    __table_args__: ClassVar = {"schema": "academic"}

    id: Mapped[UUID] = mapped_column(
        init=False,
        primary_key=True,
        default_factory=uuid4,
        server_default=func.gen_random_uuid(),
    )
    name: Mapped[str]
    lattes_id: Mapped[str] = mapped_column(unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(init=False, server_default=func.now())
    institutions: Mapped[list[ResearcherInstitution]] = relationship(
        init=False,
        back_populates="researcher",
        cascade="all, delete-orphan",
        default_factory=list,
    )
    collections: Mapped[list[ResearcherCollection]] = relationship(
        init=False,
        back_populates="researcher",
        cascade="all, delete-orphan",
        default_factory=list,
    )


@mapped_as_dataclass(table_registry)
class ResearcherInstitution:
    __tablename__ = "researcher_institutions"
    __table_args__ = (
        UniqueConstraint(
            "researcher_id", "institution_id", name="uq_researcher_institution"
        ),
        {"schema": "academic"},
    )

    id: Mapped[UUID] = mapped_column(
        init=False,
        primary_key=True,
        default_factory=uuid4,
        server_default=func.gen_random_uuid(),
    )
    researcher_id: Mapped[UUID] = mapped_column(
        ForeignKey("academic.researchers.id", ondelete="CASCADE")
    )
    institution_id: Mapped[UUID] = mapped_column(
        ForeignKey("academic.institutions.id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(init=False, server_default=func.now())

    researcher: Mapped[Researcher] = relationship(
        init=False, back_populates="institutions"
    )
    institution: Mapped[Institution] = relationship(
        init=False, back_populates="researchers"
    )


@mapped_as_dataclass(table_registry)
class ResearcherCollection:
    __tablename__ = "researcher_collections"
    __table_args__ = (
        UniqueConstraint(
            "researcher_id", "collection_id", name="uq_researcher_collection"
        ),
        {"schema": "academic"},
    )

    id: Mapped[UUID] = mapped_column(
        init=False,
        primary_key=True,
        default_factory=uuid4,
        server_default=func.gen_random_uuid(),
    )
    researcher_id: Mapped[UUID] = mapped_column(
        ForeignKey("academic.researchers.id", ondelete="CASCADE")
    )
    collection_id: Mapped[UUID] = mapped_column(
        ForeignKey("academic.collections.id", ondelete="RESTRICT")
    )
    attributes: Mapped[dict] = mapped_column(
        JSONB,
        default_factory=dict,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        init=False, server_default=func.now()
    )

    researcher: Mapped[Researcher] = relationship(
        init=False, back_populates="collections"
    )
    collection: Mapped[Collection] = relationship(
        init=False, back_populates="researchers"
    )
