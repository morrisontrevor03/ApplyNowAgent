import asyncio
import logging

import httpx
from sqlalchemy import select

from app.agents.base import BaseAgent
from app.config import settings
from app.models.contact import Contact
from app.models.user import User, UserPreferences
from app.services import quota

logger = logging.getLogger(__name__)

TARGET_COMPANY_COUNT = 25
RECRUITER_TITLES = ["Recruiter", "Technical Recruiter", "Talent Sourcer", "University Recruiter"]
BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"

EXCLUDE_KEYWORDS = {
    "vp", "vice president", "director", "chief", "ceo", "cto", "coo", "cfo",
    "founder", "owner", "partner", "head of",
}
RECRUITER_KEYWORDS = {"recruiter", "talent", "sourcer", "recruiting", "staffing"}
MANAGER_KEYWORDS = {"manager", "lead", "principal", "staff"}


def _score_title(title: str) -> float:
    t = title.lower()
    if any(k in t for k in EXCLUDE_KEYWORDS):
        return 0.0
    if any(k in t for k in RECRUITER_KEYWORDS):
        return 0.9
    if any(k in t for k in MANAGER_KEYWORDS):
        return 0.7
    return 0.75  # IC / other relevant role


class NetworkingAgent(BaseAgent):
    agent_type = "networking"
    max_iterations = 1  # unused but required by base

    async def _execute(self, **kwargs) -> dict:
        user_result = await self.db.execute(select(User).where(User.id == self.user_id))
        user = user_result.scalar_one_or_none()
        if not user:
            return {"summary": "User not found"}

        prefs_result = await self.db.execute(
            select(UserPreferences).where(UserPreferences.user_id == self.user_id)
        )
        prefs = prefs_result.scalar_one_or_none()
        if not prefs or not prefs.target_roles:
            return {"summary": "No target roles configured"}

        existing_result = await self.db.execute(
            select(Contact.linkedin_url).where(
                Contact.user_id == self.user_id,
                Contact.linkedin_url.isnot(None),
            )
        )
        self._seen_urls: set[str] = {row[0] for row in existing_result}

        companies = list(prefs.target_companies or [])
        if not companies:
            return {"summary": "No target companies configured — add companies in Settings"}

        # Search all companies directly, no Claude in the loop
        contacts: list[dict] = []
        for company in companies[:TARGET_COMPANY_COUNT]:
            for titles in [RECRUITER_TITLES, prefs.target_roles[:4]]:
                results = await self._brave_search(company, titles, max_results=5)
                contacts.extend(results)

        logger.info("Networking: %d raw profiles collected", len(contacts))

        saved = await self._save_contacts(contacts)
        return {"summary": f"Saved {saved} new contacts", "contacts_found": saved}

    async def _brave_search(self, company: str, titles: list[str], max_results: int) -> list[dict]:
        title_part = " OR ".join(f'"{t}"' for t in titles[:3])
        query = f'site:linkedin.com/in {title_part} "{company}"'

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    BRAVE_SEARCH_URL,
                    headers={
                        "Accept": "application/json",
                        "Accept-Encoding": "gzip",
                        "X-Subscription-Token": settings.brave_api_key,
                    },
                    params={"q": query, "count": min(max_results, 10)},
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.warning("Brave search error for '%s': %s", company, exc)
            return []

        people = []
        for result in (data.get("web") or {}).get("results") or []:
            url = result.get("url", "")
            if "linkedin.com/in/" not in url:
                continue
            if url in self._seen_urls:
                continue
            if url.startswith("http://"):
                url = url.replace("http://", "https://", 1)

            page_title = result.get("title", "")
            name, job_title = "", ""
            if " - " in page_title:
                parts = page_title.split(" - ", 1)
                name = parts[0].strip()
                rest = parts[1].split(" | LinkedIn")[0].strip()
                if " at " in rest.lower():
                    job_title = rest[: rest.lower().index(" at ")].strip()
                else:
                    job_title = rest.strip()

            score = _score_title(job_title)
            if score == 0.0:
                continue

            name_parts = name.split()
            people.append({
                "first_name":      name_parts[0] if name_parts else "",
                "last_name":       " ".join(name_parts[1:]) if len(name_parts) > 1 else "",
                "title":           job_title,
                "company":         company,
                "linkedin_url":    url,
                "relevance_score": score,
                "relevance_reasoning": self._reasoning(job_title),
            })
            self._seen_urls.add(url)

        logger.info("Brave '%s' -> %d profiles", company, len(people))
        await asyncio.sleep(0.5)
        return people

    def _reasoning(self, title: str) -> str:
        t = title.lower()
        if any(k in t for k in RECRUITER_KEYWORDS):
            return "Recruiter — high response rate to cold outreach"
        if any(k in t for k in MANAGER_KEYWORDS):
            return "Manager/Lead — relevant for entry-level candidates at smaller companies"
        return "IC in relevant team"

    async def _save_contacts(self, contacts: list[dict]) -> int:
        saved = 0
        for item in contacts:
            if not await quota.can_surface_contact(self.db, self.user_id):
                break

            linkedin_url = item.get("linkedin_url") or ""
            if linkedin_url:
                existing = await self.db.execute(
                    select(Contact).where(
                        Contact.user_id == self.user_id,
                        Contact.linkedin_url == linkedin_url,
                    )
                )
                if existing.scalar_one_or_none():
                    continue

            self.db.add(Contact(
                user_id=self.user_id,
                company=item.get("company", ""),
                first_name=item.get("first_name", ""),
                last_name=item.get("last_name"),
                title=item.get("title", ""),
                linkedin_url=linkedin_url or None,
                email=None,
                seniority=None,
                department=None,
                relevance_score=float(item.get("relevance_score", 0)),
                relevance_reasoning=item.get("relevance_reasoning"),
                outreach_message=None,  # generated on demand
            ))
            await self.db.flush()
            await quota.increment_contacts_surfaced(self.db, self.user_id)
            saved += 1

        await self.db.commit()
        self._contacts_saved = saved
        return saved
