import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.subscription import MonthlyUsage, Subscription


async def get_plan(db: AsyncSession, user_id: uuid.UUID) -> str:
    result = await db.execute(select(Subscription).where(Subscription.user_id == user_id))
    sub = result.scalar_one_or_none()
    return sub.plan if sub and sub.status == "active" else "free"


async def _get_or_create_usage(db: AsyncSession, user_id: uuid.UUID) -> MonthlyUsage:
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    result = await db.execute(
        select(MonthlyUsage).where(MonthlyUsage.user_id == user_id, MonthlyUsage.month == month)
    )
    usage = result.scalar_one_or_none()
    if not usage:
        usage = MonthlyUsage(user_id=user_id, month=month)
        db.add(usage)
        await db.flush()
    return usage


async def can_surface_job(db: AsyncSession, user_id: uuid.UUID) -> bool:
    plan = await get_plan(db, user_id)
    if plan == "pro":
        return True
    usage = await _get_or_create_usage(db, user_id)
    return usage.jobs_surfaced < settings.free_jobs_per_month


async def increment_jobs_surfaced(db: AsyncSession, user_id: uuid.UUID, count: int = 1):
    usage = await _get_or_create_usage(db, user_id)
    usage.jobs_surfaced += count
    await db.flush()


async def can_surface_contact(db: AsyncSession, user_id: uuid.UUID) -> bool:
    plan = await get_plan(db, user_id)
    if plan == "pro":
        return True
    usage = await _get_or_create_usage(db, user_id)
    return usage.contacts_surfaced < settings.free_contacts_per_month


async def increment_contacts_surfaced(db: AsyncSession, user_id: uuid.UUID, count: int = 1):
    usage = await _get_or_create_usage(db, user_id)
    usage.contacts_surfaced += count
    await db.flush()
