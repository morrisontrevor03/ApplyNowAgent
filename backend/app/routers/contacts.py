import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.contact import Contact
from app.models.user import User

router = APIRouter(prefix="/api/contacts", tags=["contacts"])


class ContactUpdate(BaseModel):
    outreach_status: str | None = None
    notes: str | None = None
    outreach_message: str | None = None


@router.get("")
async def list_contacts(
    company: str | None = Query(None),
    status: str | None = Query(None),
    score_min: float = Query(0.0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Contact)
        .where(Contact.user_id == current_user.id)
        .order_by(desc(Contact.relevance_score), desc(Contact.discovered_at))
    )
    if company:
        query = query.where(Contact.company.ilike(f"%{company}%"))
    if status:
        query = query.where(Contact.outreach_status == status)
    if score_min:
        query = query.where(Contact.relevance_score >= score_min)

    result = await db.execute(query)
    contacts = result.scalars().all()
    return [_serialize(c) for c in contacts]


@router.get("/{contact_id}")
async def get_contact(
    contact_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Contact).where(Contact.id == contact_id, Contact.user_id == current_user.id)
    )
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Contact not found")
    return _serialize(c)


@router.patch("/{contact_id}")
async def update_contact(
    contact_id: uuid.UUID,
    body: ContactUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Contact).where(Contact.id == contact_id, Contact.user_id == current_user.id)
    )
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Contact not found")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(c, field, value)

    await db.commit()
    await db.refresh(c)
    return _serialize(c)


def _serialize(c: Contact) -> dict:
    return {
        "id": str(c.id),
        "company": c.company,
        "first_name": c.first_name,
        "last_name": c.last_name,
        "title": c.title,
        "linkedin_url": c.linkedin_url,
        "email": c.email,
        "seniority": c.seniority,
        "department": c.department,
        "relevance_score": c.relevance_score,
        "relevance_reasoning": c.relevance_reasoning,
        "outreach_status": c.outreach_status,
        "outreach_message": c.outreach_message,
        "notes": c.notes,
        "discovered_at": c.discovered_at.isoformat() if c.discovered_at else None,
    }
