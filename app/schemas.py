from typing import Optional

from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    name: str
    email: EmailStr


class UserOut(BaseModel):
    id: int
    name: str
    email: str

    class Config:
        from_attributes = True


class ProfileUpdate(BaseModel):
    target_roles: Optional[list[str]] = None
    domains: Optional[list[str]] = None
    core_skills: Optional[list[str]] = None
    avoid_skills: Optional[list[str]] = None
    preferred_locations: Optional[list[str]] = None
    preferred_companies: Optional[list[str]] = None
    excluded_companies: Optional[list[str]] = None
    min_salary: Optional[float] = None
    work_mode: Optional[str] = None  # remote / hybrid / onsite / any
    seniority: Optional[str] = None


class ProfileOut(BaseModel):
    id: int
    user_id: int
    target_roles: list[str]
    domains: list[str]
    core_skills: list[str]
    avoid_skills: list[str]
    preferred_locations: list[str]
    preferred_companies: list[str]
    excluded_companies: list[str]
    min_salary: Optional[float]
    work_mode: Optional[str]
    seniority: Optional[str]
    skill_weights: dict

    class Config:
        from_attributes = True


class JobOut(BaseModel):
    id: int
    source: str
    title: str
    company: Optional[str]
    location: Optional[str]
    url: Optional[str]
    posted_at: Optional[str]
    score: float
    score_breakdown: dict
    feedback_status: Optional[str] = None

    class Config:
        from_attributes = True


class FeedbackIn(BaseModel):
    status: str  # applied / shortlisted / skip / rejected_salary / rejected_location
    note: Optional[str] = None
