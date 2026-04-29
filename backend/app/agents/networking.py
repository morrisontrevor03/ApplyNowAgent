import asyncio
import logging
import re

import httpx
from sqlalchemy import select

from app.agents.base import BaseAgent
from app.config import settings
from app.models.contact import Contact
from app.models.user import User, UserPreferences
from app.services import quota

logger = logging.getLogger(__name__)

TARGET_COMPANY_COUNT = 25
JUNIOR_PREFIXES = ["Junior", "Associate", "Entry Level", "New Grad"]
APOLLO_SEARCH_URL = "https://api.apollo.io/api/v1/mixed_people/api_search"

EXCLUDE_KEYWORDS = {
    "vp", "vice president", "director", "chief", "ceo", "cto", "coo", "cfo",
    "founder", "owner", "partner", "head of",
}
RECRUITER_KEYWORDS = {"recruiter", "talent", "sourcer", "recruiting", "staffing"}
JUNIOR_KEYWORDS = {"junior", "associate", "entry level", "new grad", "early career"}
MANAGER_KEYWORDS = {"manager", "lead", "principal", "staff"}


def _companies_match(target: str, found: str) -> bool:
    t = target.lower().strip()
    f = found.lower().strip()
    return t in f or f in t


def _company_domain(company_name: str) -> str:
    """Best-effort domain derivation from company name. Works for most tech companies."""
    name = company_name.lower().strip()
    for suffix in [", inc.", " inc.", ", inc", " inc", ", llc", " llc",
                   ", ltd", " ltd", ", corp.", " corp", ", co.", " co."]:
        if name.endswith(suffix):
            name = name[: -len(suffix)].strip()
    name = re.sub(r"[^a-z0-9]", "", name)
    return f"{name}.com"


def _score_title(title: str) -> float:
    t = title.lower()
    if any(k in t for k in EXCLUDE_KEYWORDS):
        return 0.0
    if any(k in t for k in RECRUITER_KEYWORDS):
        return 0.3
    if any(k in t for k in JUNIOR_KEYWORDS):
        return 0.85
    if any(k in t for k in MANAGER_KEYWORDS):
        return 0.65
    return 0.75


class NetworkingAgent(BaseAgent):
    agent_type = "networking"
    max_iterations = 1  # unused but required by base

    async def _execute(self, company: str | None = None, **kwargs) -> dict:
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

        if company:
            companies = [company]
        else:
            companies = list(prefs.target_companies or [])
        if not companies:
            return {"summary": "No target companies configured — add companies in Settings"}

        # Combine mid-level IC titles and junior variants into one list per company.
        junior_titles = [
            f"{prefix} {role}"
            for prefix in JUNIOR_PREFIXES[:2]
            for role in (prefs.target_roles[:2] or [])
        ]
        all_titles = list(prefs.target_roles[:4]) + junior_titles

        contacts: list[dict] = []
        for target_company in companies[:TARGET_COMPANY_COUNT]:
            results = await self._apollo_search(target_company, all_titles, max_results=10)
            contacts.extend(results)

        logger.info("Networking: %d raw profiles collected", len(contacts))

        saved = await self._save_contacts(contacts)
        return {"summary": f"Saved {saved} new contacts", "contacts_found": saved}

    async def _apollo_search(
        self, company: str, titles: list[str], max_results: int
    ) -> list[dict]:
        domain = _company_domain(company)

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    APOLLO_SEARCH_URL,
                    headers={
                        "Content-Type": "application/json",
                        "X-Api-Key": settings.apollo_api_key,
                        "Cache-Control": "no-cache",
                    },
                    json={
                        "q_organization_domains_list": [domain],
                        "person_titles": titles,
                        "per_page": min(max_results, 100),
                        "page": 1,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.warning("Apollo search error for '%s' (%s): %s", company, domain, exc)
            return []

        people = []
        for person in data.get("people") or []:
            linkedin_url = person.get("linkedin_url") or ""
            if not linkedin_url:
                continue
            if linkedin_url.startswith("http://"):
                linkedin_url = linkedin_url.replace("http://", "https://", 1)
            if linkedin_url in self._seen_urls:
                continue

            # Apollo returns the person's current organization — verify it matches.
            current_org = (person.get("organization") or {}).get("name", "")
            if current_org and not _companies_match(company, current_org):
                logger.debug(
                    "Skipping %s — Apollo shows current employer '%s', searched for '%s'",
                    person.get("name"), current_org, company,
                )
                continue

            title = person.get("title") or ""
            score = _score_title(title)
            if score == 0.0:
                continue

            people.append({
                "first_name": person.get("first_name") or "",
                "last_name": person.get("last_name") or "",
                "title": title,
                "company": company,
                "linkedin_url": linkedin_url,
                "relevance_score": score,
                "relevance_reasoning": self._reasoning(title),
            })
            self._seen_urls.add(linkedin_url)

        logger.info("Apollo '%s' (%s) -> %d profiles", company, domain, len(people))
        await asyncio.sleep(0.3)
        return people

    def _reasoning(self, title: str) -> str:
        t = title.lower()
        if any(k in t for k in RECRUITER_KEYWORDS):
            return "Recruiter — not a primary networking target"
        if any(k in t for k in JUNIOR_KEYWORDS):
            return "Entry/mid-level peer — great for referrals and culture insight"
        if any(k in t for k in MANAGER_KEYWORDS):
            return "Manager/Lead — useful for team context at smaller companies"
        return "Mid-level IC in relevant team"

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
                outreach_message=None,
            ))
            await self.db.flush()
            await quota.increment_contacts_surfaced(self.db, self.user_id)
            saved += 1

        await self.db.commit()
        self._contacts_saved = saved
        return saved
