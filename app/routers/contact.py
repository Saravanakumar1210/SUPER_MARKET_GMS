"""Contact form submission endpoint — stores messages in DB."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.site import ContactSubmission
from app.core.rate_limit import rate_limit

router = APIRouter(prefix="/api/v1", tags=["contact"])


class ContactFormIn(BaseModel):
    name: str
    email: EmailStr
    phone: str | None = None
    enquiry_type: str | None = None
    message: str

    @field_validator("name", "message")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Field must not be blank")
        return v

    @field_validator("name")
    @classmethod
    def name_length(cls, v: str) -> str:
        if len(v) > 150:
            raise ValueError("Name too long")
        return v

    @field_validator("message")
    @classmethod
    def message_length(cls, v: str) -> str:
        if len(v) > 5000:
            raise ValueError("Message too long (max 5000 characters)")
        return v


@router.post(
    "/contact",
    dependencies=[Depends(rate_limit(namespace="contact", limit=5, window_seconds=900))],
)
async def submit_contact_form(
    body: ContactFormIn,
    db: AsyncSession = Depends(get_db),
):
    submission = ContactSubmission(
        name=body.name,
        email=str(body.email),
        phone=(body.phone or "").strip() or None,
        enquiry_type=(body.enquiry_type or "").strip() or None,
        message=body.message,
    )
    db.add(submission)
    return {"ok": True, "message": "Your message has been received. We will be in touch shortly."}
