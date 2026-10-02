from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select, update
from starlette.concurrency import run_in_threadpool

from app.db.models import AuditLog, OAuthState, PendingGoogleOperation
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)


def cleanup(session, *, recover=False, now=None):
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(days=30)
    operations = PendingGoogleOperation
    if recover:
        while True:
            ids = select(operations.id).where(operations.status == "executing").limit(500)
            result = session.execute(
                update(operations)
                .where(operations.id.in_(ids))
                .values(
                    status="unknown", payload_encrypted=None, payload_hash="", resource_name=None
                )
            )
            session.commit()
            if result.rowcount == 0:
                break
    expired = (
        select(operations.id)
        .where(operations.status == "pending", operations.expires_at <= now)
        .limit(500)
    )
    session.execute(
        update(operations)
        .where(
            operations.id.in_(expired),
            operations.status == "pending",
            operations.expires_at <= now,
        )
        .values(status="expired", payload_encrypted=None, payload_hash="", resource_name=None)
    )
    for model, predicate in [
        (OAuthState, OAuthState.expires_at <= now),
        (AuditLog, AuditLog.created_at < cutoff),
        (
            operations,
            (operations.status.not_in(["pending", "executing"])) & (operations.updated_at < cutoff),
        ),
    ]:
        ids = select(model.id).where(predicate).limit(500)
        session.execute(delete(model).where(model.id.in_(ids)))
    session.commit()


def cleanup_once(*, recover=False):
    with SessionLocal() as session:
        cleanup(session, recover=recover)


def maintenance_lifespan(mcp_lifespan):
    @asynccontextmanager
    async def lifespan(app):
        await run_in_threadpool(cleanup_once, recover=True)

        async def periodic_cleanup():
            while True:
                await asyncio.sleep(60)
                try:
                    await run_in_threadpool(cleanup_once)
                except Exception:  # noqa: BLE001 - boundary prevents leakage or repetition of external writes
                    logger.error("Periodic retention cleanup failed")

        async with mcp_lifespan(app):
            task = asyncio.create_task(periodic_cleanup())
            try:
                yield
            finally:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

    return lifespan
