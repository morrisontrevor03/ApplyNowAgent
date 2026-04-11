import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.user import User, UserPreferences

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def run_job_scout_for_all_users():
    from app.agents.job_scout import JobScoutAgent

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User)
            .join(UserPreferences, User.id == UserPreferences.user_id)
            .where(User.is_active == True, UserPreferences.scout_enabled == True)
        )
        users = result.scalars().all()

    for user in users:
        try:
            async with AsyncSessionLocal() as db:
                agent = JobScoutAgent(db, user.id)
                await agent.run(trigger="scheduled")
        except Exception:
            logger.exception("Job scout failed for user %s", user.id)


async def run_networking_for_all_users():
    from app.agents.networking import NetworkingAgent

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User)
            .join(UserPreferences, User.id == UserPreferences.user_id)
            .where(User.is_active == True, UserPreferences.networking_enabled == True)
        )
        users = result.scalars().all()

    for user in users:
        try:
            async with AsyncSessionLocal() as db:
                agent = NetworkingAgent(db, user.id)
                await agent.run(trigger="scheduled")
        except Exception:
            logger.exception("Networking agent failed for user %s", user.id)


async def run_application_agent_for_all_users():
    from app.agents.application import ApplicationAgent

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User)
            .join(UserPreferences, User.id == UserPreferences.user_id)
            .where(User.is_active == True, UserPreferences.application_agent_enabled == True)
        )
        users = result.scalars().all()

    for user in users:
        try:
            async with AsyncSessionLocal() as db:
                agent = ApplicationAgent(db, user.id)
                await agent.run(trigger="scheduled")
        except Exception:
            logger.exception("Application agent failed for user %s", user.id)


async def reset_monthly_usage():
    """Runs on the 1st of each month at midnight to reset usage counters."""
    from sqlalchemy import delete
    from app.models.subscription import MonthlyUsage
    from datetime import datetime, timezone

    current_month = datetime.now(timezone.utc).strftime("%Y-%m")
    async with AsyncSessionLocal() as db:
        await db.execute(
            delete(MonthlyUsage).where(MonthlyUsage.month != current_month)
        )
        await db.commit()
    logger.info("Monthly usage reset complete")


def register_jobs():
    scheduler.add_job(
        run_job_scout_for_all_users,
        CronTrigger(minute="*/30"),
        id="job_scout_global",
        replace_existing=True,
        misfire_grace_time=300,
    )
    scheduler.add_job(
        run_networking_for_all_users,
        CronTrigger(hour="13,23"),
        id="networking_global",
        replace_existing=True,
        misfire_grace_time=300,
    )
    scheduler.add_job(
        run_application_agent_for_all_users,
        CronTrigger(minute="*/30"),
        id="application_global",
        replace_existing=True,
        misfire_grace_time=300,
    )
    scheduler.add_job(
        reset_monthly_usage,
        CronTrigger(day=1, hour=0, minute=0),
        id="reset_monthly_usage",
        replace_existing=True,
    )
    logger.info("APScheduler jobs registered")
