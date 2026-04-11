import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"


async def send_email(to: str, subject: str, html: str) -> bool:
    if not settings.resend_api_key:
        logger.warning("RESEND_API_KEY not set — skipping email to %s", to)
        return False

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            RESEND_API_URL,
            headers={
                "Authorization": f"Bearer {settings.resend_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "from": settings.resend_from_email,
                "to": [to],
                "subject": subject,
                "html": html,
            },
            timeout=10,
        )

    if resp.status_code not in (200, 201):
        logger.error("Resend error %s: %s", resp.status_code, resp.text)
        return False

    logger.info("Email sent to %s: %s", to, subject)
    return True


def job_alert_email(job_title: str, company: str, job_url: str, match_score: float, match_reasoning: str, app_url: str) -> str:
    score_pct = int(match_score * 100)
    return f"""
    <div style="font-family: system-ui, sans-serif; max-width: 600px; margin: 0 auto; background: #09090b; color: #fafafa; padding: 32px; border-radius: 12px;">
      <div style="margin-bottom: 24px;">
        <span style="background: #22c55e20; color: #22c55e; padding: 4px 12px; border-radius: 999px; font-size: 13px; font-weight: 600;">{score_pct}% match</span>
      </div>
      <h1 style="font-size: 22px; font-weight: 700; margin: 0 0 8px;">{job_title}</h1>
      <p style="color: #a1a1aa; margin: 0 0 20px; font-size: 15px;">{company}</p>
      <p style="color: #d4d4d8; font-size: 14px; line-height: 1.6; margin: 0 0 24px;">{match_reasoning}</p>
      <div style="display: flex; gap: 12px;">
        <a href="{app_url}" style="background: #fff; color: #09090b; padding: 10px 20px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 14px;">View Draft</a>
        <a href="{job_url}" style="background: transparent; color: #fafafa; padding: 10px 20px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 14px; border: 1px solid #27272a;">View Posting</a>
      </div>
    </div>
    """


def draft_ready_email(job_title: str, company: str, application_id: str, frontend_url: str) -> str:
    review_url = f"{frontend_url}/applications/{application_id}"
    return f"""
    <div style="font-family: system-ui, sans-serif; max-width: 600px; margin: 0 auto; background: #09090b; color: #fafafa; padding: 32px; border-radius: 12px;">
      <div style="margin-bottom: 24px;">
        <span style="background: #3b82f620; color: #3b82f6; padding: 4px 12px; border-radius: 999px; font-size: 13px; font-weight: 600;">Draft Ready</span>
      </div>
      <h1 style="font-size: 22px; font-weight: 700; margin: 0 0 8px;">Your application is drafted</h1>
      <p style="color: #a1a1aa; margin: 0 0 20px; font-size: 15px;">{job_title} · {company}</p>
      <p style="color: #d4d4d8; font-size: 14px; line-height: 1.6; margin: 0 0 24px;">
        ApplyNow has tailored your resume and written a cover letter for this role.
        Review the draft and apply before other candidates even see the posting.
      </p>
      <a href="{review_url}" style="background: #fff; color: #09090b; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 15px;">Review &amp; Apply →</a>
    </div>
    """
