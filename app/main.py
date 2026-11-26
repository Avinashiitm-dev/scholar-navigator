import uuid

from fastapi import FastAPI, HTTPException

from .agents import run
from .models import StudentProfile

app = FastAPI(title="Scholar Navigator")
QUEUE: dict[str, dict] = {}  # swap for SQLite later


@app.post("/search")
async def search(profile: StudentProfile):
    reports = await run(profile)
    all_facts = [f for r in reports for f in r.facts]
    verified = [f for f in all_facts if f.verified]
    return {
        "reports": [
            {"topic": r.topic, "facts": [f for f in r.facts if f.verified]} for r in reports
        ],
        "stats": {
            "extracted": len(all_facts),
            "verified": len(verified),
            "rejected": len(all_facts) - len(verified),
        },
    }


@app.post("/queue")
def propose(action: str, payload: dict):
    """Agents only PROPOSE actions. Nothing runs until a human approves."""
    item_id = uuid.uuid4().hex[:8]
    QUEUE[item_id] = {"id": item_id, "action": action, "payload": payload, "status": "pending"}
    return QUEUE[item_id]


@app.get("/queue")
def list_queue():
    return list(QUEUE.values())


@app.post("/queue/{item_id}/decision")
def decide(item_id: str, approve: bool):
    item = QUEUE.get(item_id)
    if not item or item["status"] != "pending":
        raise HTTPException(404, "No pending item")
    item["status"] = "approved" if approve else "rejected"
    # TODO: execute the approved action here (save draft, set reminder, ...)
    return item
