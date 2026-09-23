"""Data models for the files that live in a jobsmith data directory."""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field, HttpUrl


class Status(StrEnum):
    INTERESTED = "interested"
    APPLIED = "applied"
    SCREENING = "screening"
    INTERVIEWING = "interviewing"
    OFFER = "offer"
    REJECTED = "rejected"
    GHOSTED = "ghosted"
    WITHDRAWN = "withdrawn"

    @property
    def is_open(self) -> bool:
        return self not in {Status.OFFER, Status.REJECTED, Status.GHOSTED, Status.WITHDRAWN}


class Contact(BaseModel):
    name: str
    role: str | None = None
    email: str | None = None
    linkedin: HttpUrl | None = None


class Event(BaseModel):
    """Something that happened on an application: applied, followed up, interviewed."""

    when: date
    what: str


class Application(BaseModel):
    """One job application. Stored as YAML frontmatter; the Markdown body holds free-form notes."""

    company: str
    role: str
    url: HttpUrl | None = None
    ats: str | None = Field(default=None, description="Applicant tracking system, e.g. workday")
    status: Status = Status.INTERESTED
    applied_on: date | None = None
    next_followup: date | None = None
    resume: str | None = Field(default=None, description="Path to the resume version sent")
    cover_letter: str | None = None
    contacts: list[Contact] = []
    events: list[Event] = []
    notes: str = Field(default="", exclude=True)

    def followup_due(self, today: date | None = None) -> bool:
        today = today or date.today()
        return self.status.is_open and self.next_followup is not None and self.next_followup <= today


class Profile(BaseModel):
    """Facts about you that forms ask for over and over."""

    name: str
    email: str
    phone: str | None = None
    location: str | None = None
    linkedin: HttpUrl | None = None
    github: HttpUrl | None = None
    website: HttpUrl | None = None
    work_authorization: str | None = None
    requires_sponsorship: bool | None = None
    standard_answers: dict[str, str] = Field(
        default_factory=dict,
        description="Reusable answers to common application questions, keyed by a short name",
    )
