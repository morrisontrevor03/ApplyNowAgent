import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import engine
from app.database import Base
from app.scheduler.jobs import register_jobs, scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create upload directory
    os.makedirs(settings.upload_dir, exist_ok=True)

    # Create tables (handled by Alembic in prod, kept here for dev convenience)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:
        logger.error(f"DB init failed (tables may not exist yet): {e}")

    # Start scheduler
    try:
        register_jobs()
        scheduler.start()
        logger.info("Scheduler started")
    except Exception as e:
        logger.error(f"Scheduler failed to start: {e}")

    yield

    scheduler.shutdown()
    logger.info("Scheduler stopped")
    await engine.dispose()


app = FastAPI(
    title="ApplyNow Agent API",
    version="2.0.0",
    lifespan=lifespan,
)

_extra_origin = settings.frontend_url or ""
ALLOWED_ORIGINS = list({
    "http://localhost:3000",
    "https://apply-now-agent.vercel.app",
    *([_extra_origin] if _extra_origin else []),
})

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
from app.routers import auth, resume, jobs, applications, contacts, agents, dashboard, settings_router, stripe_webhooks  # noqa: E402

app.include_router(auth.router)
app.include_router(resume.router)
app.include_router(jobs.router)
app.include_router(applications.router)
app.include_router(contacts.router)
app.include_router(agents.router)
app.include_router(dashboard.router)
app.include_router(settings_router.router)
app.include_router(stripe_webhooks.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
