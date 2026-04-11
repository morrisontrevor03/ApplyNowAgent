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

# ── Tool definitions ───────────────────────────────────────────────────────

# Primary tool: used when PROXYCURL_API_KEY is set.
# Single call per (company, role) returns verified current employees with
# accurate titles and real LinkedIn URLs straight from LinkedIn data.
TOOL_FIND_EMPLOYEES = {
    "name": "find_employees_at_company",
    "description": (
        "Find current employees at a company. Returns verified current employees "
        "with accurate titles and confirmed LinkedIn URLs. Call this once per "
        "company per role type (e.g. once for recruiters, once for engineers)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "company_name": {
                "type": "string",
                "description": "Company name exactly as commonly known (e.g. 'Stripe', 'Airbnb')",
            },
            "role_keywords": {
                "type": "string",
                "description": (
                    "Role or title to search for within the company. "
                    "Use one focused role per call, e.g. 'Recruiter', 'Software Engineer', 'Product Manager'."
                ),
            },
            "max_results": {
                "type": "integer",
                "default": 10,
                "description": "Max employees to return (default 10, max 25)",
            },
        },
        "required": ["company_name", "role_keywords"],
    },
}

# Fallback tool: used when Proxycurl is not configured.
TOOL_GOOGLE_SEARCH = {
    "name": "google_search_people",
    "description": "Search Google for professionals at a specific company (fallback — less accurate than find_employees_at_company).",
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
    "description": "Save ranked networking contacts to the database. Call ONCE at the end with all results.",
    "input_schema": {
        "type": "object",
        "properties": {
            "contacts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "company":            {"type": "string"},
                        "first_name":         {"type": "string"},
                        "last_name":          {"type": "string"},
                        "title":              {"type": "string"},
                        "linkedin_url":       {"type": "string"},
                        "seniority":          {"type": "string"},
                        "department":         {"type": "string"},
                        "relevance_score":    {"type": "number", "description": "0.0 to 1.0"},
                        "relevance_reasoning":{"type": "string"},
                        "outreach_message":   {"type": "string", "description": "Warm 2–3 sentence coffee-chat message"},
                    },
                    "required": ["company", "first_name", "title", "linkedin_url", "relevance_score", "outreach_message"],
                },
            }
        },
        "required": ["contacts"],
    },
}


class NetworkingAgent(BaseAgent):
    agent_type = "networking"
    # 2 calls/company (recruiter + IC) × 25 companies + 1 save = ~51 iterations minimum
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

        # Seed the URL cache with contacts already in the DB so we never
        # re-fetch profiles we already have.
        existing_result = await self.db.execute(
            select(Contact.linkedin_url).where(
                Contact.user_id == self.user_id,
                Contact.linkedin_url.isnot(None),
            )
        )
        existing_urls: set[str] = {row[0] for row in existing_result}
        self._seen_urls: set[str] = set(existing_urls)

        # Per-run company LinkedIn URL cache (avoids re-resolving same company name)
        self._company_url_cache: dict[str, str | None] = {}

        use_proxycurl = bool(settings.proxycurl_api_key)
        tools = [TOOL_FIND_EMPLOYEES if use_proxycurl else TOOL_GOOGLE_SEARCH, TOOL_SAVE_CONTACTS]

        # ── Build company instructions ─────────────────────────────────────

        n = len(target_companies)
        expand = bool(getattr(prefs, "open_to_similar_companies", False))

        if target_companies:
            if expand and n < TARGET_COMPANY_COUNT:
                needed = TARGET_COMPANY_COUNT - n
                companies_instruction = (
                    f"The user listed {n} companies: {target_companies}. "
                    f"They are open to similar companies. Identify {needed} additional companies "
                    f"that are similar in domain, size, or tech stack. "
                    f"Search all {TARGET_COMPANY_COUNT} combined — do not skip any."
                )
                initial_message = (
                    f"Build a networking list starting with {target_companies} ({n} companies), "
                    f"then add {needed} similar companies for a total of {TARGET_COMPANY_COUNT}. "
                    f"For each company call find_employees_at_company twice: "
                    f"once with role_keywords='Recruiter' and once with role_keywords='{prefs.target_roles[0]}'. "
                    f"Goal: 50+ saved contacts."
                )
            else:
                companies_instruction = (
                    f"The user has {n} target companies: {target_companies}. Search all of them."
                )
                initial_message = (
                    f"Build a networking list for these {n} companies: {target_companies}. "
                    f"For each company call find_employees_at_company twice: "
                    f"once with role_keywords='Recruiter' and once with role_keywords='{prefs.target_roles[0]}'. "
                    f"Goal: 50+ saved contacts."
                )
        else:
            companies_instruction = (
                f"The user has no specific target companies. Choose {TARGET_COMPANY_COUNT} companies "
                f"that actively hire {', '.join(prefs.target_roles)} at the "
                f"{prefs.experience_level or 'entry'} level. Mix large tech, high-growth startups, "
                f"and mid-size product companies."
            )
            initial_message = (
                f"Build a networking list for a {prefs.experience_level or 'entry'}-level "
                f"{', '.join(prefs.target_roles)} job seeker. "
                f"Pick {TARGET_COMPANY_COUNT} strong companies, then for each call "
                f"find_employees_at_company twice: once for 'Recruiter' and once for "
                f"'{prefs.target_roles[0]}'. Goal: 50+ saved contacts."
            )

        data_source_note = (
            "Employee data comes from LinkedIn via Proxycurl — titles and current employment "
            "are accurate and up to date. Trust the data as-is."
            if use_proxycurl else
            "Data comes from Google search snippets which may be stale. Only include someone "
            "if the snippet clearly shows they currently work at the target company."
        )

        system_prompt = f"""You are the ApplyNow Networking Agent. Build a large, high-quality list of networking contacts.

## User profile
- Target roles: {prefs.target_roles}
- Experience level: {prefs.experience_level or "entry"}
- Preferred locations: {prefs.target_locations or ["anywhere"]}

## Companies
{companies_instruction}

## Already in database — skip these LinkedIn URLs
{list(existing_urls)[:60]}

## Data quality
{data_source_note}

## Who to include
The user is an entry-level / early-career candidate. Prioritise people likely to respond:
1. **Technical Recruiters / Talent Sourcers** — highest priority, responding is their job (score 0.85–0.95)
2. **Mid / Senior Individual Contributors** in the relevant team (score 0.70–0.85)
3. **Eng managers at smaller companies** (<500 employees) (score 0.65–0.80)

## Who to EXCLUDE (score 0.0, do not save)
C-suite, VPs, Directors, Founders, Partners — will not respond to entry-level outreach.

## Volume target
Work through ALL companies before calling save_contacts. Goal is 50+ contacts total.
Do not stop early. Two find_employees_at_company calls per company minimum.

## Outreach messages
- 2–3 sentences, warm and direct
- Reference the company or team, NOT a specific title
- Invite a conversation about the team / culture
- Never directly ask for a job or referral

Save all contacts with score >= 0.6 in a single save_contacts call at the end.
"""

        await self.run_tool_loop(system_prompt, initial_message, tools)

        contacts_saved = getattr(self, "_contacts_saved", 0)
        return {"summary": f"Saved {contacts_saved} new contacts", "contacts_found": contacts_saved}

    # ── Tool dispatch ──────────────────────────────────────────────────────

    async def dispatch_tool(self, name: str, input_data: dict) -> Any:
        if name == "find_employees_at_company":
            return await self._find_employees(
                input_data["company_name"],
                input_data["role_keywords"],
                min(int(input_data.get("max_results", 10)), 25),
            )
        if name == "google_search_people":
            return await self._google_search_people(
                input_data["company"],
                input_data["title_keywords"],
            )
        if name == "save_contacts":
            return await self._save_contacts(input_data["contacts"])
        return f"Unknown tool: {name}"

    # ── Proxycurl: company resolve ─────────────────────────────────────────

    async def _resolve_company_url(self, client: httpx.AsyncClient, company_name: str) -> str | None:
        if company_name in self._company_url_cache:
            return self._company_url_cache[company_name]

        try:
            resp = await client.get(
                "https://nubela.co/proxycurl/api/linkedin/company/resolve",
                params={"company_name": company_name},
                headers={"Authorization": f"Bearer {settings.proxycurl_api_key}"},
                timeout=15,
            )
            if resp.status_code != 200:
                self._company_url_cache[company_name] = None
                return None
            url = resp.json().get("url")
            self._company_url_cache[company_name] = url
            return url
        except Exception as exc:
            logger.warning("Company resolve error for '%s': %s", company_name, exc)
            self._company_url_cache[company_name] = None
            return None

    # ── Proxycurl: employee listing ────────────────────────────────────────

    async def _find_employees(self, company_name: str, role_keywords: str, max_results: int) -> str:
        async with httpx.AsyncClient() as client:
            company_url = await self._resolve_company_url(client, company_name)
            if not company_url:
                return json.dumps({"error": f"Could not find LinkedIn page for '{company_name}'"})

            try:
                resp = await client.get(
                    "https://nubela.co/proxycurl/api/linkedin/company/employees/",
                    params={
                        "linkedin_company_profile_url": company_url,
                        "role_search": role_keywords,
                        "employment_status": "current",
                        "page_size": max_results,
                        "enrich_profiles": "enrich",
                    },
                    headers={"Authorization": f"Bearer {settings.proxycurl_api_key}"},
                    timeout=30,
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                logger.warning("Employee listing error for '%s': %s", company_name, exc)
                return json.dumps({"error": str(exc)})

        employees = []
        for emp in data.get("employees") or []:
            profile = emp.get("profile") or {}
            linkedin_url = (
                emp.get("profile_url")
                or (profile.get("public_identifier") and
                    f"https://www.linkedin.com/in/{profile['public_identifier']}/")
            )

            # Skip if already in DB or seen this run
            if linkedin_url and linkedin_url in self._seen_urls:
                continue

            # Derive current title from experiences (ends_at=null) or headline
            experiences = profile.get("experiences") or []
            current_exp = next((e for e in experiences if e.get("ends_at") is None), None)
            title = (
                current_exp.get("title", "")
                if current_exp
                else profile.get("occupation") or profile.get("headline", "")
            )

            employee = {
                "first_name": profile.get("first_name", ""),
                "last_name":  profile.get("last_name", ""),
                "title":      title,
                "company":    company_name,
                "linkedin_url": linkedin_url,
                "headline":   profile.get("headline", ""),
            }

            if linkedin_url:
                self._seen_urls.add(linkedin_url)

            employees.append(employee)

        logger.info(
            "find_employees '%s' role='%s' → %d results",
            company_name, role_keywords, len(employees),
        )
        return json.dumps({"company": company_name, "role_search": role_keywords, "employees": employees})

    # ── Google fallback ────────────────────────────────────────────────────

    async def _google_search_people(self, company: str, title_keywords: str) -> str:
        if not settings.google_api_key or not settings.google_search_engine_id:
            return json.dumps({"error": "Neither Proxycurl nor Google API is configured"})

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
            {
                "title":   item.get("title", ""),
                "url":     item.get("link", ""),
                "snippet": item.get("snippet", ""),
            }
            for item in data.get("items", [])
            if "linkedin.com/in/" in item.get("link", "")
            and item.get("link") not in self._seen_urls
        ]
        return json.dumps({"company": company, "results": results, "warning": "Proxycurl not configured — verify current employment from snippet before saving"})

    # ── Save contacts ──────────────────────────────────────────────────────

    async def _save_contacts(self, contacts_data: list[dict]) -> str:
        saved = 0

        for item in contacts_data:
            if not await quota.can_surface_contact(self.db, self.user_id):
                break

            linkedin_url = item.get("linkedin_url") or ""

            # Skip duplicates (belt-and-suspenders check against DB)
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
        return f"Saved {saved} contacts."
