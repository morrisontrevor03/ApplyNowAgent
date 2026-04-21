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

TARGET_COMPANY_COUNT = 25

# Job title levels to exclude — senior leadership won't respond to cold messages.
PDL_EXCLUDED_LEVELS = ["director", "vp", "c_suite", "owner", "partner", "founder"]

PDL_PEOPLE_SEARCH_URL = "https://api.peopledatalabs.com/v5/person/search"

# ── Tool definitions ───────────────────────────────────────────────────────

TOOL_FIND_PEOPLE = {
    "name": "find_people_at_company",
    "description": (
        "Search People Data Labs for current employees at a company by role. "
        "Returns real people with verified current titles, LinkedIn URLs, and email addresses. "
        "Senior leaders (VP+, C-suite, Directors) are automatically excluded. "
        "Call this once per company per role type."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "company_name": {
                "type": "string",
                "description": "Company name as commonly known (e.g. 'Stripe', 'Airbnb')",
            },
            "titles": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Job titles to search for. Use one focused group per call. "
                    "Examples: ['Recruiter', 'Technical Recruiter', 'Talent Sourcer'] "
                    "or ['Software Engineer', 'SWE', 'Software Developer']"
                ),
            },
            "max_results": {
                "type": "integer",
                "default": 10,
                "description": "Max people to return (default 10)",
            },
        },
        "required": ["company_name", "titles"],
    },
}

TOOL_GOOGLE_FALLBACK = {
    "name": "google_search_people",
    "description": "Fallback: search Google for professionals at a company. Less accurate — use only when PDL is unavailable.",
    "input_schema": {
        "type": "object",
        "properties": {
            "company": {"type": "string"},
            "title_keywords": {"type": "string"},
        },
        "required": ["company", "title_keywords"],
    },
}

TOOL_SAVE_CONTACTS = {
    "name": "save_contacts",
    "description": "Save all networking contacts to the database. Call ONCE at the end with every contact collected.",
    "input_schema": {
        "type": "object",
        "properties": {
            "contacts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "company":             {"type": "string"},
                        "first_name":          {"type": "string"},
                        "last_name":           {"type": "string"},
                        "title":               {"type": "string"},
                        "linkedin_url":        {"type": "string"},
                        "email":               {"type": "string"},
                        "seniority":           {"type": "string"},
                        "department":          {"type": "string"},
                        "relevance_score":     {"type": "number", "description": "0.0 to 1.0"},
                        "relevance_reasoning": {"type": "string"},
                        "outreach_message":    {"type": "string", "description": "Warm 2-3 sentence coffee-chat message"},
                    },
                    "required": ["company", "first_name", "title", "relevance_score", "outreach_message"],
                },
            }
        },
        "required": ["contacts"],
    },
}


class NetworkingAgent(BaseAgent):
    agent_type = "networking"
    # 2 calls/company x 25 companies + 1 save = ~51; give headroom
    max_iterations = 80

    # ── Entry point ────────────────────────────────────────────────────────

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

        target_companies = prefs.target_companies or []

        # Track URLs seen this run (seeded from DB) to avoid duplicates
        existing_result = await self.db.execute(
            select(Contact.linkedin_url).where(
                Contact.user_id == self.user_id,
                Contact.linkedin_url.isnot(None),
            )
        )
        self._seen_urls: set[str] = {row[0] for row in existing_result}

        use_pdl = bool(settings.pdl_api_key)
        tools = [TOOL_FIND_PEOPLE if use_pdl else TOOL_GOOGLE_FALLBACK, TOOL_SAVE_CONTACTS]

        # ── Company instructions ───────────────────────────────────────────

        n = len(target_companies)
        expand = bool(getattr(prefs, "open_to_similar_companies", False))

        if target_companies:
            if expand and n < TARGET_COMPANY_COUNT:
                needed = TARGET_COMPANY_COUNT - n
                companies_instruction = (
                    f"The user listed {n} companies: {target_companies}. "
                    f"They are open to similar companies. Identify {needed} additional companies "
                    f"similar in domain, size, or tech stack, for a combined total of {TARGET_COMPANY_COUNT}."
                )
                initial_message = (
                    f"Build a networking list. Start with {target_companies}, then add {needed} similar "
                    f"companies (total {TARGET_COMPANY_COUNT}). For EACH company call find_people_at_company "
                    f"twice: once with titles=['Recruiter','Technical Recruiter','Talent Sourcer'] and once "
                    f"with titles={prefs.target_roles[:3]}. Goal: 50+ contacts saved."
                )
            else:
                companies_instruction = f"The user's {n} target companies: {target_companies}. Search all of them."
                initial_message = (
                    f"Build a networking list for {target_companies}. For EACH company call "
                    f"find_people_at_company twice: once with titles=['Recruiter','Technical Recruiter','Talent Sourcer'] "
                    f"and once with titles={prefs.target_roles[:3]}. Goal: 50+ contacts saved."
                )
        else:
            companies_instruction = (
                f"No target companies set. Choose {TARGET_COMPANY_COUNT} companies that actively "
                f"hire {', '.join(prefs.target_roles)} at the {prefs.experience_level or 'entry'} level. "
                f"Mix large tech, high-growth startups, and mid-size product companies."
            )
            initial_message = (
                f"Build a networking list for a {prefs.experience_level or 'entry'}-level "
                f"{', '.join(prefs.target_roles)} job seeker. Pick {TARGET_COMPANY_COUNT} companies, "
                f"then for each call find_people_at_company twice: once for recruiters and once for "
                f"{prefs.target_roles[0]}. Goal: 50+ contacts saved."
            )

        data_note = (
            "PDL data is sourced directly — job_company_name reflects CURRENT employer. Trust the results."
            if use_pdl else
            "Fallback: Google snippets may be stale. Only include someone if the snippet clearly shows "
            "they currently work at that company."
        )

        system_prompt = f"""You are the ApplyNow Networking Agent. Build a large, high-quality networking list for the user.

## User profile
- Target roles: {prefs.target_roles}
- Experience level: {prefs.experience_level or "entry"}
- Preferred locations: {prefs.target_locations or ["anywhere"]}

## Companies
{companies_instruction}

## Skip these LinkedIn URLs (already in database)
{list(self._seen_urls)[:60]}

## Data
{data_note}

## Who to prioritise
The user is entry-level. Target people most likely to respond to a cold message:

1. **Technical Recruiters / Talent Sourcers** - score 0.85-0.95 (responding is their job)
2. **Mid / Senior Individual Contributors** in the relevant team - score 0.70-0.85
3. **Engineering Managers at smaller companies** (<500 employees) - score 0.65-0.80

VP+, Directors, C-suite, and Founders are already filtered out at the API level.
If any slip through, score them 0.0 and exclude them.

## Volume
Work through ALL {TARGET_COMPANY_COUNT} companies before calling save_contacts.
Do not stop early. Two find_people_at_company calls per company minimum.
Goal: 50+ contacts total.

## Outreach messages
- 2-3 sentences, warm and direct
- Reference the company or team - not a specific title
- Ask to learn about the team / culture
- Never directly ask for a job or referral

Call save_contacts ONCE at the end with all contacts that score >= 0.6.
"""

        await self.run_tool_loop(system_prompt, initial_message, tools)

        contacts_saved = getattr(self, "_contacts_saved", 0)
        return {"summary": f"Saved {contacts_saved} new contacts", "contacts_found": contacts_saved}

    # ── Tool dispatch ──────────────────────────────────────────────────────

    async def dispatch_tool(self, name: str, input_data: dict) -> Any:
        if name == "find_people_at_company":
            return await self._pdl_search(
                input_data["company_name"],
                input_data["titles"],
                int(input_data.get("max_results", 10)),
            )
        if name == "google_search_people":
            return await self._google_fallback(input_data["company"], input_data["title_keywords"])
        if name == "save_contacts":
            return await self._save_contacts(input_data["contacts"])
        return f"Unknown tool: {name}"

    # ── PDL people search ──────────────────────────────────────────────────

    async def _pdl_search(self, company_name: str, titles: list[str], max_results: int) -> str:
        try:
            # Build title match clauses (any of the provided titles)
            title_clauses = [{"match_phrase": {"job_title": t.lower()}} for t in titles]

            query = {
                "bool": {
                    "must": [
                        {"term": {"job_company_name": company_name.lower()}},
                        {
                            "bool": {
                                "should": title_clauses,
                                "minimum_should_match": 1,
                            }
                        },
                    ],
                    "must_not": [
                        {"terms": {"job_title_levels": PDL_EXCLUDED_LEVELS}}
                    ],
                }
            }

            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.post(
                    PDL_PEOPLE_SEARCH_URL,
                    headers={
                        "Content-Type": "application/json",
                        "X-Api-Key": settings.pdl_api_key,
                    },
                    json={
                        "query": query,
                        "size": min(max_results, 25),
                        "pretty": False,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.warning("PDL search error for '%s': %s", company_name, exc)
            return json.dumps({"error": str(exc)})

        people = []
        for p in (data.get("data") or []):
            linkedin_url = p.get("linkedin_url") or ""
            # Normalise to https
            if linkedin_url and linkedin_url.startswith("http://"):
                linkedin_url = linkedin_url.replace("http://", "https://", 1)

            if linkedin_url and linkedin_url in self._seen_urls:
                continue

            # PDL stores emails as a list of objects: [{"address": "...", "type": "..."}]
            emails = p.get("emails") or []
            email = ""
            for e in emails:
                if isinstance(e, dict) and e.get("address"):
                    email = e["address"]
                    break
            if not email:
                email = p.get("work_email") or ""

            # PDL job_title_levels is a list; take first entry as seniority
            levels = p.get("job_title_levels") or []
            seniority = levels[0] if levels else ""

            person = {
                "first_name":   p.get("first_name", ""),
                "last_name":    p.get("last_name", ""),
                "title":        p.get("job_title", ""),
                "company":      p.get("job_company_name") or company_name,
                "linkedin_url": linkedin_url,
                "email":        email,
                "seniority":    seniority,
            }

            if linkedin_url:
                self._seen_urls.add(linkedin_url)

            people.append(person)

        logger.info("PDL '%s' titles=%s -> %d people", company_name, titles, len(people))
        return json.dumps({"company": company_name, "titles_searched": titles, "people": people})

    # ── Google fallback ────────────────────────────────────────────────────

    async def _google_fallback(self, company: str, title_keywords: str) -> str:
        if not settings.google_api_key or not settings.google_search_engine_id:
            return json.dumps({"error": "Neither PDL nor Google API is configured"})

        query = f'site:linkedin.com/in ({title_keywords}) "at {company}"'
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

        results = [
            {"title": item.get("title", ""), "url": item.get("link", ""), "snippet": item.get("snippet", "")}
            for item in data.get("items", [])
            if "linkedin.com/in/" in item.get("link", "")
            and item.get("link") not in self._seen_urls
        ]
        return json.dumps({
            "company": company,
            "results": results,
            "warning": "PDL not configured — only include contacts where snippet confirms current employment",
        })

    # ── Save contacts ──────────────────────────────────────────────────────

    async def _save_contacts(self, contacts_data: list[dict]) -> str:
        saved = 0

        for item in contacts_data:
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

            contact = Contact(
                user_id=self.user_id,
                company=item.get("company", ""),
                first_name=item.get("first_name", ""),
                last_name=item.get("last_name"),
                title=item.get("title", ""),
                linkedin_url=linkedin_url or None,
                email=item.get("email") or None,
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
        return f"Saved {saved} contacts."
