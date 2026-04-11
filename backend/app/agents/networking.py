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
    max_iterations = 60  # needs many tool calls: 2-3 searches × 20-30 companies + 1 save

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

        # Per-run Proxycurl cache: url -> verified profile dict (or None if not a current employee).
        # Prevents duplicate API calls when the same URL surfaces in multiple company searches.
        # Seeded with existing DB contacts so we never call Proxycurl for URLs we already have.
        self._proxycurl_cache: dict[str, dict | None] = {url: None for url in existing_urls}

        TARGET_COMPANY_COUNT = 25

        if target_companies:
            n = len(target_companies)
            expand = getattr(prefs, "open_to_similar_companies", False)

            if expand and n < TARGET_COMPANY_COUNT:
                needed = TARGET_COMPANY_COUNT - n
                companies_instruction = (
                    f"The user listed {n} target companies: {target_companies}. "
                    f"They are open to similar companies. Use your knowledge to identify "
                    f"{needed} additional companies that are similar in size, stage, or domain. "
                    f"Combined, search all {TARGET_COMPANY_COUNT} companies — do not skip any."
                )
                initial_message = (
                    f"Do a thorough networking search. Start with the user's {n} listed companies: "
                    f"{target_companies}. Then identify {needed} similar companies and search those too, "
                    f"for a total of {TARGET_COMPANY_COUNT} companies. "
                    f"For each company run at least two searches — one for recruiters/talent sourcers "
                    f"and one for {', '.join(prefs.target_roles or ['engineers'])}. "
                    f"Goal: 5–10 verified contacts per company."
                )
            else:
                companies_instruction = (
                    f"The user has {n} target companies: {target_companies}. "
                    f"Search ALL of them — do not skip any."
                )
                initial_message = (
                    f"Do a thorough networking search across ALL of these companies: {target_companies}. "
                    f"For each company run at least two searches — one targeting recruiters/talent sourcers "
                    f"and one targeting {', '.join(prefs.target_roles or ['engineers'])}. "
                    f"Goal: 5–10 verified contacts per company."
                )
        else:
            companies_instruction = (
                f"The user has no specific target companies. Use your knowledge to identify "
                f"{TARGET_COMPANY_COUNT} companies that actively hire {', '.join(prefs.target_roles)} "
                f"at the {prefs.experience_level or 'entry'} level. Mix large tech companies, "
                f"high-growth startups, and mid-size firms. Search all of them."
            )
            initial_message = (
                f"Do a thorough networking search for a {prefs.experience_level or 'entry'}-level "
                f"{', '.join(prefs.target_roles)} job seeker. Pick {TARGET_COMPANY_COUNT} relevant "
                f"companies and search each one. For every company run at least two searches — one for "
                f"recruiters and one for engineers/ICs. Goal: 100+ verified contacts total."
            )

        system_prompt = f"""You are the ApplyNow Networking Agent. Your job is to build a large, high-quality list of networking contacts for the user.

User profile:
- Target roles: {prefs.target_roles or ["Software Engineer"]}
- Experience level: {prefs.experience_level or "entry"}
- Preferred locations: {prefs.target_locations or ["anywhere"]}

{companies_instruction}

Already known contacts (skip these LinkedIn URLs): {list(existing_urls)[:50]}

## Volume goal
This run should produce as many valid contacts as possible — ideally 50–100+.
Search every target company. For each company, make multiple google_search_people calls with different title_keywords:
1. "Recruiter OR Talent Sourcer OR Technical Recruiter"
2. The user's target role keywords (e.g. "Software Engineer OR SWE")
3. "Engineering Manager" (for smaller/mid-size companies only)

Do NOT stop after a few companies. Work through all of them before calling save_contacts.

## Who to target — people most likely to respond to an entry-level candidate
- Technical Recruiters and Talent Sourcers (highest priority — responding is literally their job)
- Individual contributors: mid/senior engineers, analysts, PMs (non-director)
- Recent graduates or people 1–5 years into their career (more empathetic)
- Eng managers at companies with fewer than 500 employees

## Who to EXCLUDE
- C-suite, VP-level, Director-level, Founders — will not respond
- Anyone VP+ or C-suite: score 0.0

## Current employment
Results from Proxycurl are already verified as current employees — trust them.
If you receive raw Google snippets instead, apply strict judgment: only include someone if the snippet clearly shows they currently work at that company. When in doubt, exclude.

## Scoring
- Technical Recruiters: 0.85–0.95
- Mid/senior ICs in a relevant team: 0.70–0.85
- Eng managers at smaller companies: 0.65–0.80
- Anyone VP+ or C-suite: 0.0

## Outreach messages
- 2–3 sentences, warm and direct
- Reference their company, not a specific title (titles may shift)
- Ask to learn about the team/culture, not for a job or referral

Include all contacts with score >= 0.6. Call save_contacts once at the end with all results.
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

    async def _verify_linkedin_profile(
        self, client: httpx.AsyncClient, linkedin_url: str, target_company: str
    ) -> dict | None:
        """
        Calls Proxycurl to fetch a real-time LinkedIn profile.
        Returns enriched profile dict if the person currently works at target_company,
        otherwise returns None.
        Results are cached for the lifetime of the run so duplicate URLs
        (same person surfacing from multiple company searches) cost zero extra calls.
        """
        cache = getattr(self, "_proxycurl_cache", {})
        if linkedin_url in cache:
            cached = cache[linkedin_url]
            # Still check company match even on cache hit — same profile may
            # be a current employee of company A but not company B.
            if cached is None:
                return None
            if target_company.lower() in cached.get("company", "").lower():
                return cached
            return None

        try:
            resp = await client.get(
                "https://nubela.co/proxycurl/api/v2/linkedin",
                params={"url": linkedin_url, "use_cache": "if-present"},
                headers={"Authorization": f"Bearer {settings.proxycurl_api_key}"},
                timeout=20,
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("Proxycurl error for %s: %s", linkedin_url, exc)
            cache[linkedin_url] = None
            return None

        # Current position = experience entry where ends_at is null
        experiences = data.get("experiences") or []
        current = [e for e in experiences if e.get("ends_at") is None]
        if not current:
            cache[linkedin_url] = None
            return None

        profile = {
            "first_name": data.get("first_name", ""),
            "last_name": data.get("last_name", ""),
            "title": current[0].get("title", data.get("occupation", "")),
            "company": current[0].get("company", ""),
            "linkedin_url": linkedin_url,
        }
        cache[linkedin_url] = profile  # cache the full profile regardless of company match

        current_company = profile["company"]
        if target_company.lower() not in current_company.lower():
            logger.debug(
                "Skipping %s — current employer '%s' != '%s'",
                linkedin_url, current_company, target_company,
            )
            return None

        return profile

    async def _search_people(self, company: str, title_keywords: str) -> str:
        if not settings.google_api_key or not settings.google_search_engine_id:
            return json.dumps({"error": "Google API not configured"})

        # "at Company" biases Google toward profiles where the company appears as a current role
        query = f'site:linkedin.com/in ({title_keywords}) "at {company}"'

        async with httpx.AsyncClient(timeout=15) as google_client:
            try:
                resp = await google_client.get(
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

        linkedin_urls = [
            item.get("link", "")
            for item in data.get("items", [])
            if "linkedin.com/in/" in item.get("link", "")
        ]

        # If Proxycurl is configured, verify current employment in real-time.
        # Otherwise fall back to raw Google snippets so the agent still works
        # without the key (with stale-data caveats).
        if settings.proxycurl_api_key:
            verified = []
            async with httpx.AsyncClient() as px_client:
                for url in linkedin_urls:
                    profile = await self._verify_linkedin_profile(px_client, url, company)
                    if profile:
                        verified.append(profile)
            return json.dumps({"company": company, "verified_current_employees": verified})
        else:
            results = [
                {"title": item.get("title", ""), "url": item.get("link", ""), "snippet": item.get("snippet", "")}
                for item in data.get("items", [])
            ]
            return json.dumps({"company": company, "results": results, "warning": "Proxycurl not configured — titles may be stale"})

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
