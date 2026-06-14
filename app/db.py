import datetime
import os

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "db")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "job_agent.db")

engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    profile = relationship("Profile", back_populates="user", uselist=False)


class Profile(Base):
    __tablename__ = "profiles"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)

    target_roles = Column(JSON, default=list)
    domains = Column(JSON, default=list)
    core_skills = Column(JSON, default=list)
    avoid_skills = Column(JSON, default=list)
    preferred_locations = Column(JSON, default=list)
    preferred_companies = Column(JSON, default=list)
    excluded_companies = Column(JSON, default=list)
    min_salary = Column(Float, nullable=True)
    work_mode = Column(String, nullable=True)  # remote / hybrid / onsite / any
    seniority = Column(String, nullable=True)

    resume_text = Column(Text, nullable=True)
    skill_weights = Column(JSON, default=dict)  # learned weights from feedback

    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    user = relationship("User", back_populates="profile")


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("dedupe_key", name="uq_job_dedupe_key"),)

    id = Column(Integer, primary_key=True)
    source = Column(String, nullable=False)
    source_id = Column(String, nullable=True)
    title = Column(String, nullable=False)
    company = Column(String, nullable=True)
    location = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    url = Column(String, nullable=True)
    posted_at = Column(String, nullable=True)
    dedupe_key = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class Match(Base):
    __tablename__ = "matches"
    __table_args__ = (UniqueConstraint("user_id", "job_id", name="uq_match_user_job"),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    score = Column(Float, nullable=False)
    score_breakdown = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    job = relationship("Job")


class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    status = Column(String, nullable=False)  # applied / shortlisted / skip / rejected_salary / rejected_location
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


def init_db():
    Base.metadata.create_all(engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
