"""Extract raw text and a rough skill list from an uploaded resume (PDF)."""

import re

import pdfplumber

from app.skills_taxonomy import SKILL_KEYWORDS


def extract_text_from_pdf(path: str) -> str:
    text_parts = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            text_parts.append(page_text)
    return "\n".join(text_parts)


def extract_skills(text: str) -> list[str]:
    text_lower = text.lower()
    found = []
    for skill in SKILL_KEYWORDS:
        # word-boundary-ish match, allow skills with symbols like c++ / ci/cd
        pattern = re.escape(skill.lower())
        if re.search(pattern, text_lower):
            found.append(skill)
    return found


def parse_resume(path: str) -> dict:
    """Parse a resume file (PDF) and return raw text + extracted skills.

    This is intentionally lightweight (keyword matching) for the MVP.
    The user still confirms/edits target roles, locations, salary, etc.
    via the profile endpoints.
    """
    if path.lower().endswith(".pdf"):
        text = extract_text_from_pdf(path)
    else:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()

    skills = extract_skills(text)
    return {
        "resume_text": text,
        "extracted_skills": skills,
    }
