"""Evaluation harness running 10 diverse student profiles through the pipeline."""
import argparse
import asyncio
from collections import Counter
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.agents import run
from app.models import StudentProfile

EVAL_PROFILES: list[tuple[str, StudentProfile]] = [
    (
        "Bihar OBC UG B.Sc.",
        StudentProfile(
            description="First-year B.Sc. student studying at a government college",
            state="Bihar",
            category="OBC",
            income_inr=300000,
            course_level="undergraduate",
        ),
    ),
    (
        "Maharashtra SC Engineering",
        StudentProfile(
            description="Second-year B.E. Computer Engineering student at a state university",
            state="Maharashtra",
            category="SC",
            income_inr=200000,
            course_level="undergraduate",
        ),
    ),
    (
        "Tamil Nadu ST Class 12",
        StudentProfile(
            description="Class 12 government higher secondary school student",
            state="Tamil Nadu",
            category="ST",
            income_inr=150000,
            course_level="higher secondary",
        ),
    ),
    (
        "Uttar Pradesh Minority PG",
        StudentProfile(
            description="M.A. Economics first-year student from a minority community",
            state="Uttar Pradesh",
            category="Minority",
            income_inr=180000,
            course_level="postgraduate",
        ),
    ),
    (
        "Karnataka General EWS Medical",
        StudentProfile(
            description="First-year MBBS student from economically weaker section",
            state="Karnataka",
            category="General",
            income_inr=450000,
            course_level="undergraduate",
        ),
    ),
    (
        "West Bengal General Girl Merit",
        StudentProfile(
            description="Female student pursuing B.A. Honours with 85% in Class 12",
            state="West Bengal",
            category="General",
            income_inr=250000,
            course_level="undergraduate",
        ),
    ),
    (
        "Rajasthan OBC Diploma Polytechnic",
        StudentProfile(
            description="Diploma in Mechanical Engineering student at government polytechnic",
            state="Rajasthan",
            category="OBC",
            income_inr=120000,
            course_level="diploma",
        ),
    ),
    (
        "Assam ST PhD Research",
        StudentProfile(
            description="Full-time PhD scholar in life sciences at a central university",
            state="Assam",
            category="ST",
            income_inr=350000,
            course_level="PhD",
        ),
    ),
    (
        "Kerala SC ITI Vocational",
        StudentProfile(
            description="Electrician trade student enrolled in government ITI",
            state="Kerala",
            category="SC",
            income_inr=100000,
            course_level="vocational",
        ),
    ),
    (
        "Odisha Minority Class 10",
        StudentProfile(
            description="Class 10 student in a government-aided high school",
            state="Odisha",
            category="Minority",
            income_inr=90000,
            course_level="secondary",
        ),
    ),
]


def load_dotenv(env_path: Path) -> None:
    """Populate os.environ from .env without overwriting existing variables."""
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


async def evaluate(profiles: list[tuple[str, StudentProfile]]) -> int:
    total_extracted = 0
    total_verified = 0
    total_rejected = 0
    failures = 0

    for idx, (label, profile) in enumerate(profiles, start=1):
        try:
            reports = await run(profile)
        except Exception as exc:
            failures += 1
            print(f"[{idx}/{len(profiles)}] {label}: ERROR ({type(exc).__name__}: {exc})")
            continue

        all_facts = [f for r in reports for f in r.facts]
        extracted = len(all_facts)
        verified = sum(1 for f in all_facts if f.verified)
        rejected_facts = [f for f in all_facts if not f.verified]
        rejected = len(rejected_facts)

        total_extracted += extracted
        total_verified += verified
        total_rejected += rejected

        reasons = Counter((f.reason or "(no reason)").strip() for f in rejected_facts)
        top_reasons = ", ".join(f"{reason} ({count})" for reason, count in reasons.most_common(3))
        if not top_reasons:
            top_reasons = "none"

        print(
            f"[{idx}/{len(profiles)}] {label} | "
            f"extracted={extracted} verified={verified} rejected={rejected} | "
            f"top_rejects: {top_reasons}"
        )

    rate = (total_verified / total_extracted * 100.0) if total_extracted else 0.0
    print(
        f"\nSUMMARY: profiles={len(profiles)} errors={failures} "
        f"extracted={total_extracted} verified={total_verified} rejected={total_rejected} "
        f"verified_rate={rate:.1f}%"
    )
    return 1 if failures == len(profiles) else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run accuracy evaluation on 10 student profiles.")
    parser.add_argument("--no-cache", action="store_true", help="Bypass the on-disk page cache.")
    parser.add_argument("--limit", type=int, default=len(EVAL_PROFILES), help="Number of profiles to run.")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    if args.no_cache:
        os.environ["BYPASS_PAGE_CACHE"] = "1"

    return asyncio.run(evaluate(EVAL_PROFILES[: args.limit]))


if __name__ == "__main__":
    raise SystemExit(main())
