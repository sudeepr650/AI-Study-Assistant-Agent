import json
import os
from pathlib import Path

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"


class StudyError(Exception):
    """An actionable error suitable for the dashboard."""


def generate(instruction, payload, schema):
    """Use structured output and independently validate the returned JSON."""
    from dotenv import load_dotenv
    from google import genai
    from google.genai import types
    from pydantic import ValidationError

    load_dotenv(BASE / ".env")
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise StudyError("Add your Gemini API key to .env and restart Streamlit.")
    try:
        with genai.Client(api_key=key, http_options=types.HttpOptions(timeout=45000)) as client:
            reply = client.models.generate_content(
                model=os.getenv("GEMINI_MODEL") or "gemini-3.5-flash-lite",
                contents=json.dumps(payload, ensure_ascii=False),
                config=types.GenerateContentConfig(
                    system_instruction=instruction, response_mime_type="application/json",
                    response_json_schema=schema.model_json_schema(),
                ),
            )
            return schema.model_validate_json(reply.text or "")
    except ValidationError as exc:
        raise StudyError("Gemini returned an incomplete or invalid result. Please retry.") from exc
    except Exception as exc:
        code = getattr(exc, "code", None)
        hint = {400: "Check your API key and model.", 403: "Check API access.",
                404: "Choose an available GEMINI_MODEL in .env.",
                429: "Check your quota or retry later."}.get(code, "Check your connection and retry.")
        raise StudyError(f"Gemini request failed. {hint}") from exc
