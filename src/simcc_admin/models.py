from __future__ import annotations

from datetime import datetime
from typing import ClassVar
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import (
    Mapped,
    mapped_as_dataclass,
    mapped_column,
    registry,
    relationship,
)

table_registry = registry()


@mapped_as_dataclass(table_registry)
class User:
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        init=False,
        primary_key=True,
        default_factory=uuid4,
        server_default=func.gen_random_uuid(),
    )
    username: Mapped[str] = mapped_column(unique=True)
    password: Mapped[str | None] = mapped_column(nullable=True, default=None)
    email: Mapped[str | None] = mapped_column(unique=True, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(init=False, server_default=func.now())
    oauth_accounts: Mapped[list[OAuthAccount]] = relationship(
        init=False,
        back_populates="user",
        cascade="all, delete-orphan",
        default_factory=list,
    )


@mapped_as_dataclass(table_registry)
class OAuthAccount:
    __tablename__ = "oauth_accounts"
    __table_args__ = (
        UniqueConstraint("provider", "provider_user_id", name="uq_provider_user"),
    )

    id: Mapped[UUID] = mapped_column(
        init=False,
        primary_key=True,
        default_factory=uuid4,
        server_default=func.gen_random_uuid(),
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    provider: Mapped[str]
    provider_user_id: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(init=False, server_default=func.now())
    user: Mapped[User] = relationship(init=False, back_populates="oauth_accounts")


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
