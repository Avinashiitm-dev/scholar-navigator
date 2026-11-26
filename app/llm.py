import json
import os
import re

from anthropic import AsyncAnthropic

MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5")
_client: AsyncAnthropic | None = None


def parse_json(text: str):
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    return json.loads(text)


async def ask_json(system: str, user: str, max_tokens: int = 3000):
    global _client
    _client = _client or AsyncAnthropic()
    r = await _client.messages.create(
        model=MODEL, max_tokens=max_tokens, system=system,
        messages=[{"role": "user", "content": user}],
    )
    return parse_json(r.content[0].text)
