import asyncio
import json

from .llm import ask_json
from .models import Fact, ResearchJob, SchemeReport, StudentProfile
from .providers import discover, fetch_page
from .verify import quote_in_page

PLANNER_SYS = """You plan research for an Indian student scholarship finder.
Return ONLY JSON: {"jobs":[{"topic":str,"search_query":str}]}.
Max 4 jobs, each a different source family (central govt, the student's state
govt, category-specific e.g. SC/ST/OBC/minority, merit or means based).
Queries must target official government sources."""

EXTRACT_SYS = """Extract scholarship facts from the page text.
Return ONLY JSON: {"facts":[{"claim":str,"quote":str}]}.
Rules: quote must be copied EXACTLY, character for character, from the page
(one full sentence or line). The claim must be fully supported by that quote
alone. Cover eligibility, amount, deadline, documents. Never use outside
knowledge. If nothing is relevant return {"facts":[]}."""

JUDGE_SYS = """You are a strict fact checker. For each item decide whether the
QUOTE alone fully supports the CLAIM (same numbers, dates, conditions).
Return ONLY JSON: {"results":[{"i":int,"supported":bool,"reason":str}]}."""


async def plan(profile: StudentProfile) -> list[ResearchJob]:
    data = await ask_json(PLANNER_SYS, profile.model_dump_json())
    return [ResearchJob(**j) for j in data["jobs"][:4]]


async def _extract(url: str, page: str) -> list[Fact]:
    data = await ask_json(EXTRACT_SYS, page[:30000])
    return [Fact(source_url=url, **f) for f in data.get("facts", [])]


async def research(job: ResearchJob):
    urls = await discover(job.search_query)
    fetched = await asyncio.gather(*(fetch_page(u) for u in urls), return_exceptions=True)
    pages = {u: p for u, p in zip(urls, fetched) if isinstance(p, str) and p}
    extracted = await asyncio.gather(*(_extract(u, p) for u, p in pages.items()))
    return [f for group in extracted for f in group], pages


async def check(facts: list[Fact], pages: dict[str, str]) -> list[Fact]:
    candidates = []
    for f in facts:
        if quote_in_page(f.quote, pages.get(f.source_url, "")):
            candidates.append(f)
        else:
            f.reason = "quote not found on source page"
    if candidates:
        items = [{"i": i, "claim": f.claim, "quote": f.quote} for i, f in enumerate(candidates)]
        data = await ask_json(JUDGE_SYS, json.dumps(items))
        verdict = {r["i"]: r for r in data["results"]}
        for i, f in enumerate(candidates):
            v = verdict.get(i, {})
            f.verified = bool(v.get("supported"))
            f.reason = v.get("reason", "")
    return facts


async def run(profile: StudentProfile) -> list[SchemeReport]:
    async def one(job: ResearchJob) -> SchemeReport:
        facts, pages = await research(job)
        return SchemeReport(topic=job.topic, facts=await check(facts, pages))

    return await asyncio.gather(*(one(j) for j in await plan(profile)))
