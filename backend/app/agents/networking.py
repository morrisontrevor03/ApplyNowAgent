import asyncio
import json
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
RECRUITER_TITLES = ["Recruiter", "Technical Recruiter", "Talent Sourcer", "University Recruiter"]
BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"

EXCLUDE_TITLE_KEYWORDS = {
    "vp", "vice president", "director", "chief", "ceo", "cto", "coo", "cfo",
    "founder", "owner", "partner", "head of",
}


class NetworkingAgent(BaseAgent):
    agent_type = "networking"
    max_iterations = 3  # only used for company selection

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

        # Step 1: resolve company list (1 Claude call if needed)
        companies = await self._resolve_companies(prefs)
        logger.info("Networking: searching %d companies", len(companies))

        # Step 2: search all companies directly — no Claude loop
        raw_contacts: list[dict] = []
        for company in companies:
            for titles in [RECRUITER_TITLES, prefs.target_roles[:4]]:
                results = await self._brave_search(company, titles, max_results=5)
                raw_contacts.extend(results)

        logger.info("Networking: %d raw profiles collected", len(raw_contacts))
        if not raw_contacts:
            return {"summary": "No profiles found via search", "contacts_found": 0}

        # Step 3: score + write outreach in batches (~5 Claude calls total)
        scored = await self._score_and_generate_outreach(raw_contacts, prefs)
        logger.info("Networking: %d contacts scored >= 0.6", len(scored))

        # Step 4: save
        saved = await self._save_contacts_list(scored)
        return {"summary": f"Saved {saved} new contacts", "contacts_found": saved}

    # ── Company resolution ─────────────────────────────────────────────────

    async def _resolve_companies(self, prefs: UserPreferences) -> list[str]:
        companies = list(prefs.target_companies or [])
        expand = bool(getattr(prefs, "open_to_similar_companies", False))

        if companies and not expand:
            return companies[:TARGET_COMPANY_COUNT]

        needed = TARGET_COMPANY_COUNT - len(companies)
        if needed <= 0:
            return companies[:TARGET_COMPANY_COUNT]

        context = (
            f"The user already targets: {companies}. Add {needed} similar companies "
            f"in the same domain or tech stack."
            if companies else
            f"Pick {needed} companies that actively hire {prefs.target_roles} at "
            f"{prefs.experience_level or 'entry'} level. Mix large tech, high-growth "
            f"startups, and mid-size product companies."
        )

        try:
            resp = await self.client.messages.create(
                model=self.model,
                max_tokens=400,
                messages=[{
                    "role": "user",
                    "content": f"{context}\n\nReturn ONLY a JSON array of company names, nothing else. Example: [\"Stripe\", \"Plaid\"]",
                }],
            )
            text = resp.content[0].text.strip()
            match = re.search(r'\[.*?\]', text, re.DOTALL)
            if match:
                new_companies = json.loads(match.group())
                companies = companies + [c for c in new_companies if c not in companies]
        except Exception as exc:
            logger.warning("Company selection failed: %s", exc)

        return companies[:TARGET_COMPANY_COUNT]

    # ── Brave Search ───────────────────────────────────────────────────────

    async def _brave_search(self, company_name: str, titles: list[str], max_results: int) -> list[dict]:
        title_part = " OR ".join(f'"{t}"' for t in titles[:3])
        query = f'site:linkedin.com/in {title_part} "{company_name}"'

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
            logger.warning("Brave search error for '%s': %s", company_name, exc)
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

            title_lower = job_title.lower()
            if any(kw in title_lower for kw in EXCLUDE_TITLE_KEYWORDS):
                continue

            name_parts = name.split()
            person = {
                "first_name": name_parts[0] if name_parts else "",
                "last_name":  " ".join(name_parts[1:]) if len(name_parts) > 1 else "",
                "title":      job_title,
                "company":    company_name,
                "linkedin_url": url,
                "email":      "",
                "seniority":  "",
                "snippet":    result.get("description", "")[:300],
            }

            self._seen_urls.add(url)
            people.append(person)

        logger.info("Brave '%s' -> %d profiles", company_name, len(people))
        await asyncio.sleep(0.5)
        return people

    # ── Score + outreach (batched) ─────────────────────────────────────────

    async def _score_and_generate_outreach(self, contacts: list[dict], prefs: UserPreferences) -> list[dict]:
        valid = [c for c in contacts if c.get("first_name") and c.get("linkedin_url")]
        if not valid:
            return []

        all_scored: list[dict] = []
        for i in range(0, len(valid), 25):
            batch = valid[i : i + 25]
            scored = await self._score_batch(batch, prefs)
            all_scored.extend(scored)
        return all_scored

    async def _score_batch(self, contacts: list[dict], prefs: UserPreferences) -> list[dict]:
        contacts_json = json.dumps(
            [
                {
                    "id": i,
                    "first_name": c["first_name"],
                    "last_name":  c.get("last_name", ""),
                    "title":      c.get("title", ""),
                    "company":    c.get("company", ""),
                    "snippet":    c.get("snippet", "")[:200],
                }
                for i, c in enumerate(contacts)
            ],
            indent=2,
        )

        prompt = f"""Score these LinkedIn contacts for a {prefs.experience_level or "entry"}-level {", ".join(prefs.target_roles)} job seeker.

Scoring guide:
- Technical Recruiters / Talent Sourcers: 0.85-0.95
- ICs in the relevant team (engineers, PMs, etc): 0.70-0.85
- Engineering Managers at small/mid companies: 0.65-0.80
- VP / Director / C-suite / Founder / Owner: 0.0 — exclude

Rules:
- Only include someone if their snippet confirms they CURRENTLY work at that company.
- If the snippet is empty or unclear, set include=false.
- For included contacts, write a warm 2-3 sentence outreach message that references the company/team, asks to learn about the culture, and never asks for a job or referral.

Contacts:
{contacts_json}

Return ONLY a valid JSON array (no markdown, no explanation):
[{{"id": 0, "relevance_score": 0.9, "relevance_reasoning": "...", "outreach_message": "...", "include": true}}]"""

        try:
            resp = await self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            text = resp.content[0].text.strip()
            match = re.search(r'\[.*\]', text, re.DOTALL)
            if not match:
                return []
            scored_results = json.loads(match.group())
        except Exception as exc:
            logger.warning("Scoring batch failed: %s", exc)
            return []

        result = []
        for sr in scored_results:
            if not sr.get("include") or float(sr.get("relevance_score", 0)) < 0.6:
                continue
            idx = int(sr["id"])
            if idx >= len(contacts):
                continue
            result.append({
                **contacts[idx],
                "relevance_score":     float(sr["relevance_score"]),
                "relevance_reasoning": sr.get("relevance_reasoning", ""),
                "outreach_message":    sr.get("outreach_message", ""),
            })
        return result

    # ── Save ───────────────────────────────────────────────────────────────

    async def _save_contacts_list(self, contacts_data: list[dict]) -> int:
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
        return saved
