"""Small helper around the Gemini API, so the rest of the code stays simple."""
from google import genai
from google.genai import errors, types

from app import config

# Create one Gemini client and reuse it for every request
_client = genai.Client(api_key=config.GEMINI_API_KEY)


class QuotaExceeded(Exception):
    """Raised when Gemini says we've used up our free quota (HTTP 429)."""


def generate_structured(
    system_prompt: str,
    user_text: str,
    schema,
    model: str | None = None,
    image_bytes: bytes | None = None,
    image_mime: str | None = None,
):
    """Ask Gemini for an answer that follows a fixed structure (a Pydantic model).

    Gemini returns JSON matching `schema`, and the SDK turns it into a
    Python object, so we never have to parse messy free text ourselves.
    `model` lets each step pick a model (defaults to the main CHAT_MODEL).
    If `image_bytes` is given, the picture is sent together with the text,
    so Gemini can "see" it (Gemini is multimodal: text, images, and audio).
    """
    if image_bytes:
        contents = [types.Part.from_bytes(data=image_bytes, mime_type=image_mime), user_text]
    else:
        contents = user_text

    try:
        response = _client.models.generate_content(
            model=model or config.CHAT_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,     # the rules the model must follow
                response_mime_type="application/json",  # reply as JSON only
                response_schema=schema,               # the exact fields we want back
                temperature=0.3,                      # low = more consistent, less random
            ),
        )
    except errors.ClientError as error:
        # Turn Google's quota error into our own clear exception
        if error.code == 429:
            raise QuotaExceeded() from error
        raise
    return response.parsed  # an instance of `schema`