import json
import os
import re

from google import genai
from google.genai import types

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
_client: genai.Client | None = None


def parse_json(text: str):
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    return json.loads(text)


async def ask_json(system: str, user: str, max_tokens: int = 4096):
    global _client
    _client = _client or genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    r = await _client.aio.models.generate_content(
        model=MODEL,
        contents=user,
        config=types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens,
            response_mime_type="application/json",
        ),
    )
    return parse_json(r.text)
