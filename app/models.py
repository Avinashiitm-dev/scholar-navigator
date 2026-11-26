from pydantic import BaseModel


class StudentProfile(BaseModel):
    description: str              # free text, English or Hindi
    state: str | None = None
    category: str | None = None   # General / OBC / SC / ST / Minority
    income_inr: int | None = None # annual family income
    course_level: str | None = None


class ResearchJob(BaseModel):
    topic: str
    search_query: str


class Fact(BaseModel):
    claim: str
    source_url: str
    quote: str                    # exact text copied from the page
    verified: bool = False
    reason: str = ""


class SchemeReport(BaseModel):
    topic: str
    facts: list[Fact]
