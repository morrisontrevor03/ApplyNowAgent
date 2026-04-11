import logging
from datetime import datetime

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


async def search_adzuna(keywords: str, location: str = "", max_results: int = 20) -> list[dict]:
    if not settings.adzuna_app_id or not settings.adzuna_app_key:
        logger.warning("Adzuna credentials not set")
        return []

    params = {
        "app_id": settings.adzuna_app_id,
        "app_key": settings.adzuna_app_key,
        "results_per_page": max_results,
        "what": keywords,
        "content-type": "application/json",
    }
    if location:
        params["where"] = location
    if settings.free_jobs_per_month:
        params["salary_min"] = 0

    url = "https://api.adzuna.com/v1/api/jobs/us/search/1"

    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.error("Adzuna error: %s", exc)
            return []

    results = []
    for item in data.get("results", []):
        results.append({
            "external_id": item.get("id", ""),
            "source": "adzuna",
            "title": item.get("title", ""),
            "company": item.get("company", {}).get("display_name", "Unknown"),
            "location": item.get("location", {}).get("display_name", ""),
            "description": item.get("description", ""),
            "url": item.get("redirect_url", ""),
            "salary_min": int(item["salary_min"]) if item.get("salary_min") else None,
            "salary_max": int(item["salary_max"]) if item.get("salary_max") else None,
            "employment_type": item.get("contract_type"),
            "posted_at": item.get("created"),
        })
    return results


async def search_jsearch(query: str, location: str = "", max_results: int = 10) -> list[dict]:
    if not settings.jsearch_api_key:
        logger.warning("JSearch API key not set")
        return []

    full_query = f"{query} {location}".strip()
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.get(
                "https://jsearch.p.rapidapi.com/search",
                params={"query": full_query, "num_pages": "1", "page": "1"},
                headers={
                    "X-RapidAPI-Key": settings.jsearch_api_key,
                    "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
                },
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.error("JSearch error: %s", exc)
            return []

    results = []
    for item in data.get("data", [])[:max_results]:
        results.append({
            "external_id": item.get("job_id", ""),
            "source": "jsearch",
            "title": item.get("job_title", ""),
            "company": item.get("employer_name", "Unknown"),
            "location": f"{item.get('job_city', '')} {item.get('job_state', '')} {item.get('job_country', '')}".strip(),
            "description": item.get("job_description", ""),
            "url": item.get("job_apply_link") or item.get("job_google_link", ""),
            "salary_min": item.get("job_min_salary"),
            "salary_max": item.get("job_max_salary"),
            "employment_type": item.get("job_employment_type"),
            "posted_at": None,
        })
    return results


async def search_google_jobs(query: str, max_results: int = 10) -> list[dict]:
    """Uses Google Custom Search as a fallback for job discovery."""
    if not settings.google_api_key or not settings.google_search_engine_id:
        return []

    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.get(
                "https://www.googleapis.com/customsearch/v1",
                params={
                    "key": settings.google_api_key,
                    "cx": settings.google_search_engine_id,
                    "q": f"{query} job posting site:jobs.lever.co OR site:boards.greenhouse.io OR site:linkedin.com/jobs",
                    "num": min(max_results, 10),
                },
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.error("Google Custom Search error: %s", exc)
            return []

    results = []
    for item in data.get("items", []):
        results.append({
            "external_id": item.get("link", ""),
            "source": "google",
            "title": item.get("title", ""),
            "company": item.get("displayLink", ""),
            "location": "",
            "description": item.get("snippet", ""),
            "url": item.get("link", ""),
            "salary_min": None,
            "salary_max": None,
            "employment_type": None,
            "posted_at": None,
        })
    return results
