import json
import logging
from typing import Any

import httpx
from sqlalchemy import select

from app.agents.base import BaseAgent
from app.config import settings
from app.models.contact import Contact
from app.models.user import User, UserPreferences
from app.services import quota

logger = logging.getLogger(__name__)

TOOLS = [
    {
        "name": "google_search_people",
        "description": "Search Google for professionals at a specific company using Google Custom Search API.",
        "input_schema": {
            "type": "object",
            "properties": {
                "company": {"type": "string"},
                "title_keywords": {"type": "string", "description": "e.g. 'Engineering Manager OR Staff Engineer OR Recruiter'"},
            },
            "required": ["company", "title_keywords"],
        },
    },
    {
        "name": "save_contacts",
        "description": "Save ranked networking contacts to the database.",
        "input_schema": {
            "type": "object",
            "properties": {
                "contacts": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "company": {"type": "string"},
                            "first_name": {"type": "string"},
                            "last_name": {"type": "string"},
                            "title": {"type": "string"},
                            "linkedin_url": {"type": "string"},
                            "seniority": {"type": "string"},
                            "department": {"type": "string"},
                            "relevance_score": {"type": "number", "description": "0.0 to 1.0"},
                            "relevance_reasoning": {"type": "string"},
                            "outreach_message": {"type": "string", "description": "Personalized 2-3 sentence coffee chat message"},
                        },
                        "required": ["company", "first_name", "title", "linkedin_url", "relevance_score", "outreach_message"],
                    },
                }
            },
            "required": ["contacts"],
        },
    },
]


class NetworkingAgent(BaseAgent):
    agent_type = "networking"

    async def _execute(self, **kwargs) -> dict:
        user_result = await self.db.execute(select(User).where(User.id == self.user_id))
        user = user_result.scalar_one_or_none()
        if not user:
            return {"summary": "User not found"}

        prefs_result = await self.db.execute(select(UserPreferences).where(UserPreferences.user_id == self.user_id))
        prefs = prefs_result.scalar_one_or_none()
        if not prefs or not prefs.target_roles:
            return {"summary": "No target roles configured"}

        # If no explicit target companies, search for top companies hiring for their roles
        target_companies = prefs.target_companies if prefs.target_companies else []

        # Existing contacts to avoid duplicates
        existing_result = await self.db.execute(
            select(Contact.linkedin_url).where(Contact.user_id == self.user_id, Contact.linkedin_url.isnot(None))
        )
        existing_urls = {row[0] for row in existing_result}

        if target_companies:
            companies_instruction = f"Target companies to search: {target_companies}"
            initial_message = (
                f"Find networking contacts at these companies: {target_companies}. "
                f"I'm a {prefs.experience_level or 'mid'}-level {', '.join(prefs.target_roles or ['engineer'])}."
            )
        else:
            companies_instruction = (
                f"The user has no specific target companies. Use your knowledge to identify "
                f"5–8 well-known companies that actively hire {', '.join(prefs.target_roles)} "
                f"and search for contacts there."
            )
            initial_message = (
                f"Find networking contacts relevant to a {prefs.experience_level or 'mid'}-level "
                f"{', '.join(prefs.target_roles)} job search. Pick 5–8 strong companies to search."
            )

        system_prompt = f"""You are the ApplyNow Networking Agent. Find professionals at companies for the user to reach out to for coffee chats.

User profile:
- Target roles: {prefs.target_roles or ["Software Engineer"]}
- Experience level: {prefs.experience_level or "entry"}
- Preferred locations: {prefs.target_locations or ["anywhere"]}

{companies_instruction}

Already known contacts (LinkedIn URLs — skip these): {list(existing_urls)[:30]}

## Who to target
The user is an entry-level/early-career candidate. Target people who are MOST LIKELY TO RESPOND to a cold message from someone junior:
- Individual contributors: Software Engineers (mid/senior level), Analysts, PMs (non-director)
- Technical Recruiters and Talent Sourcers (they respond by definition — it's their job)
- People who graduated within the last 5–8 years (more empathetic to job seekers)
- Team leads or eng managers at small/mid-size companies

## Who to EXCLUDE
DO NOT save contacts who hold these roles — they are extremely unlikely to respond to entry-level outreach:
- C-suite (CEO, CTO, CPO, CFO, COO, etc.)
- VP-level (VP of Engineering, VP of Product, etc.)
- Director-level (Director of Engineering, Director of Product, etc.)
- Founders / Co-founders
- Partners / Principals at VC firms

## Stale data warning
Google search results are often months or years out of date. A snippet may show someone's OLD title from a previous job.
- Do NOT assert that someone "currently" holds a title unless you are certain
- Write outreach messages that are role-agnostic — reference their background or company, NOT a specific current title
- Set the `title` field to what the search result shows, but treat it as approximate

## Scoring
Rank each person 0.0–1.0 on how likely a coffee chat leads to a referral or warm intro:
- Recruiters at the target company: 0.85–0.95
- Mid/senior ICs in the relevant team: 0.70–0.85
- Eng managers at smaller companies: 0.65–0.80
- Anyone VP+ or C-suite: score them 0.0 (they will be filtered out)

## Outreach message rules
- 2–3 sentences max
- Do NOT mention a specific current job title (it may be wrong)
- Reference their company or general background instead
- Be direct about wanting to learn more about the team / culture
- Do NOT ask for a job or referral directly

Only include contacts with score >= 0.6. Call save_contacts once with all results.
"""

        await self.run_tool_loop(system_prompt, initial_message, TOOLS)

        contacts_saved = getattr(self, "_contacts_saved", 0)
        return {"summary": f"Saved {contacts_saved} new contacts", "contacts_found": contacts_saved}

    async def dispatch_tool(self, name: str, input_data: dict) -> Any:
        if name == "google_search_people":
            return await self._search_people(input_data["company"], input_data["title_keywords"])

        if name == "save_contacts":
            return await self._save_contacts(input_data["contacts"])

        return f"Unknown tool: {name}"

    async def _search_people(self, company: str, title_keywords: str) -> str:
        if not settings.google_api_key or not settings.google_search_engine_id:
            return json.dumps({"error": "Google API not configured"})

        query = f'site:linkedin.com/in ({title_keywords}) "{company}"'

        async with httpx.AsyncClient(timeout=15) as client:
            try:
                resp = await client.get(
                    "https://www.googleapis.com/customsearch/v1",
                    params={
                        "key": settings.google_api_key,
                        "cx": settings.google_search_engine_id,
                        "q": query,
                        "num": 10,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                logger.error("Google search error: %s", exc)
                return json.dumps({"error": str(exc)})

        results = []
        for item in data.get("items", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": item.get("snippet", ""),
            })

        return json.dumps({"company": company, "results": results})

    async def _save_contacts(self, contacts_data: list[dict]) -> str:
        saved = 0

        for item in contacts_data:
            if not await quota.can_surface_contact(self.db, self.user_id):
                break

            # De-duplicate by LinkedIn URL
            linkedin_url = item.get("linkedin_url", "")
            if linkedin_url:
                existing = await self.db.execute(
                    select(Contact).where(
                        Contact.user_id == self.user_id,
                        Contact.linkedin_url == linkedin_url,
                    )
                )
                if existing.scalar_one_or_none():
                    continue

            contact = Contact(
                user_id=self.user_id,
                company=item.get("company", ""),
                first_name=item.get("first_name", ""),
                last_name=item.get("last_name"),
                title=item.get("title", ""),
                linkedin_url=linkedin_url or None,
                seniority=item.get("seniority"),
                department=item.get("department"),
                relevance_score=float(item.get("relevance_score", 0)),
                relevance_reasoning=item.get("relevance_reasoning"),
                outreach_message=item.get("outreach_message", ""),
            )
            self.db.add(contact)
            await self.db.flush()
            await quota.increment_contacts_surfaced(self.db, self.user_id)
            saved += 1

        await self.db.commit()
        self._contacts_saved = saved
        return f"Saved {saved} contacts"
