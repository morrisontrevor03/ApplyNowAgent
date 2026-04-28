import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db, AsyncSessionLocal
from app.dependencies import get_current_user
from app.models.agent_run import AgentRun
from app.models.user import User

router = APIRouter(prefix="/api/agents", tags=["agents"])


class SingleCompanyRequest(BaseModel):
    company: str


async def _run_agent(agent_class, user_id, trigger: str, **kwargs):
    async with AsyncSessionLocal() as db:
        agent = agent_class(db, user_id)
        await agent.run(trigger=trigger, **kwargs)


@router.post("/job-scout/run")
async def trigger_job_scout(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    from app.agents.job_scout import JobScoutAgent
    background_tasks.add_task(_run_agent, JobScoutAgent, current_user.id, "manual")
    return {"ok": True, "message": "Job Scout started"}


@router.post("/networking/run")
async def trigger_networking(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    from app.agents.networking import NetworkingAgent
    background_tasks.add_task(_run_agent, NetworkingAgent, current_user.id, "manual")
    return {"ok": True, "message": "Networking Agent started"}


@router.post("/networking/run-single")
async def trigger_networking_single(
    body: SingleCompanyRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    from app.agents.networking import NetworkingAgent
    background_tasks.add_task(
        _run_agent, NetworkingAgent, current_user.id, "manual", company=body.company
    )
    return {"ok": True, "message": f"Networking Agent started for {body.company}"}


@router.post("/application/run")
async def trigger_application_agent(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    from app.agents.application import ApplicationAgent
    background_tasks.add_task(_run_agent, ApplicationAgent, current_user.id, "manual")
    return {"ok": True, "message": "Application Agent started"}


@router.get("/test-brave")
async def test_brave(current_user: User = Depends(get_current_user)):
    """Quick sanity-check: hits Brave Search with a Stripe recruiter query."""
    if not settings.brave_api_key:
        return {"error": "BRAVE_API_KEY not configured"}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                    "X-Subscription-Token": settings.brave_api_key,
                },
                params={"q": 'site:linkedin.com/in "Recruiter" "Stripe"', "count": 5},
            )
            data = resp.json()
            results = (data.get("web") or {}).get("results") or []
            return {
                "status_code": resp.status_code,
                "result_count": len(results),
                "sample": [
                    {"title": r.get("title"), "url": r.get("url"), "snippet": r.get("description", "")[:150]}
                    for r in results[:3]
                ],
            }
    except Exception as exc:
        return {"error": str(exc)}


@router.get("/runs")
async def list_runs(
    agent_type: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(AgentRun)
        .where(AgentRun.user_id == current_user.id)
        .order_by(desc(AgentRun.started_at))
        .limit(limit)
    )
    if agent_type:
        query = query.where(AgentRun.agent_type == agent_type)

    result = await db.execute(query)
    runs = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "agent_type": r.agent_type,
            "trigger": r.trigger,
            "status": r.status,
            "jobs_found": r.jobs_found,
            "contacts_found": r.contacts_found,
            "applications_created": r.applications_created,
            "tokens_used": r.tokens_used,
            "duration_ms": r.duration_ms,
            "error_message": r.error_message,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        }
        for r in runs
    ]
