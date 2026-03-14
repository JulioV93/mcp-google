from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    external_subject: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    tenant_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    google_connection: Mapped[GoogleConnection | None] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )
    oauth_states: Mapped[list[OAuthState]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    audit_logs: Mapped[list[AuditLog]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    pending_google_operations: Mapped[list[PendingGoogleOperation]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class GoogleConnection(TimestampMixin, Base):
    __tablename__ = "google_connections"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    google_email: Mapped[str] = mapped_column(String(320), nullable=False)
    google_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")
    granted_scopes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    access_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="google_connection")

    __table_args__ = (UniqueConstraint("user_id", name="uq_google_connections_user_id"),)


class OAuthState(Base):
    __tablename__ = "oauth_states"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    state: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    code_verifier: Mapped[str] = mapped_column(Text, nullable=False)
    requested_scopes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped[User] = relationship(back_populates="oauth_states")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    arguments_redacted: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    result_status: Mapped[str] = mapped_column(String(50), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped[User] = relationship(back_populates="audit_logs")


class PendingGoogleOperation(TimestampMixin, Base):
    __tablename__ = "pending_google_operations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    operation_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    operation_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    resource_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payload_normalized: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    payload_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending", index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="pending_google_operations")
