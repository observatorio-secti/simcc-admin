from __future__ import annotations

from datetime import datetime

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

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
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

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    provider: Mapped[str]
    provider_user_id: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(init=False, server_default=func.now())
    user: Mapped[User] = relationship(init=False, back_populates="oauth_accounts")
