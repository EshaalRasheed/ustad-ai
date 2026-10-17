"""Ustad AI web server: receives the learner's voice, text, or picture and returns a spoken Urdu answer."""
import base64
import os

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.llm import QuotaExceeded
from app.tutor import ask_ustad, check_answer
from app.voice import speak_async, transcribe

app = FastAPI(title="Ustad AI", description="Urdu voice tutor for learners of any age")

MAX_AUDIO_BYTES = 5 * 1024 * 1024  # reject recordings bigger than 5 MB
MAX_IMAGE_BYTES = 8 * 1024 * 1024  # reject pictures bigger than 8 MB
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}
BUSY_URDU = "استاد ابھی آرام کر رہا ہے۔ آج کے سوالوں کی حد پوری ہو گئی ہے، تھوڑی دیر بعد دوبارہ آئیں۔"
NOT_HEARD_URDU = "معاف کیجیے، مجھے آپ کی آواز صاف سنائی نہیں دی۔ براہِ مہربانی دوبارہ بولیں۔"


@app.exception_handler(QuotaExceeded)
async def quota_exceeded_handler(request: Request, exc: QuotaExceeded):
    """When the free AI quota runs out, reply politely instead of crashing (HTTP 500)."""
    return JSONResponse(status_code=429, content={"detail": BUSY_URDU})


# ---------- Request bodies for typed input ----------

class TextQuestion(BaseModel):
    """A typed question (fallback when there's no microphone)."""
    question: str = Field(min_length=1, max_length=500)


class TextAnswer(BaseModel):
    """A typed answer to Ustad's quiz question."""
    check_question: str = Field(min_length=1, max_length=500)
    expected_answer: str = Field(min_length=1, max_length=500)
    answer: str = Field(min_length=1, max_length=500)


# ---------- Shared helpers ----------

def to_base64(audio_mp3: bytes) -> str:
    """Audio is sent as base64 text so it fits inside the JSON reply."""
    return base64.b64encode(audio_mp3).decode("ascii")


async def read_audio(audio: UploadFile) -> bytes:
    """Read an uploaded recording and reject empty or oversized files."""
    data = await audio.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty recording")
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Recording too long")
    return data


async def read_image(image: UploadFile) -> bytes:
    """Read an uploaded picture and reject wrong types or oversized files."""
    if image.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=415, detail="Please upload a JPG, PNG, or WEBP picture")
    data = await image.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty picture")
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Picture too large")
    return data


async def not_heard_reply() -> dict:
    """Friendly spoken 'please say it again' when the audio wasn't understood."""
    return {
        "not_heard": True,
        "explanation_urdu": NOT_HEARD_URDU,
        "feedback_urdu": NOT_HEARD_URDU,
        "audio_base64": to_base64(await speak_async(NOT_HEARD_URDU)),
    }


async def build_reply(question: str, image_bytes: bytes | None = None, image_mime: str | None = None) -> dict:
    """Run Ustad's brain on a question (and optional picture), then turn the answer into speech."""
    # ask_ustad is normal (blocking) code, so run it in a worker thread;
    # this keeps the server free to handle other learners at the same time
    result = await run_in_threadpool(ask_ustad, question, image_bytes, image_mime)

    spoken_text = f"{result['explanation_urdu']} {result['check_question_urdu']}".strip()
    audio_mp3 = await speak_async(spoken_text)
    return {"question": question, **result, "audio_base64": to_base64(audio_mp3)}


async def build_feedback(check_question: str, expected_answer: str, child_answer: str) -> dict:
    """Check the learner's quiz answer, then turn the feedback into speech."""
    result = await run_in_threadpool(check_answer, check_question, expected_answer, child_answer)
    audio_mp3 = await speak_async(result.feedback_urdu)
    return {
        "child_answer": child_answer,
        "is_correct": result.is_correct,
        "feedback_urdu": result.feedback_urdu,
        "audio_base64": to_base64(audio_mp3),
    }


# ---------- Endpoints ----------

@app.get("/api/health")
def health():
    """Simple check used by hosting platforms to see if the app is alive."""
    return {"status": "ok"}


@app.post("/api/ask-audio")
async def ask_audio(audio: UploadFile = File(...)):
    """Voice question: WAV recording in -> transcription + spoken answer out."""
    data = await read_audio(audio)
    question = await run_in_threadpool(transcribe, data, "audio/wav")
    if not question:
        return await not_heard_reply()
    return await build_reply(question)


@app.post("/api/ask-text")
async def ask_text(body: TextQuestion):
    """Typed question: text in -> spoken answer out."""
    return await build_reply(body.question.strip())


@app.post("/api/ask-image")
async def ask_image(
    image: UploadFile = File(...),             # the picture (required)
    question: str = Form(""),                  # optional typed question about it
    audio: UploadFile | None = File(None),     # optional spoken question about it
):
    """Picture question: photo (+ optional voice or text question) in -> spoken explanation out."""
    image_bytes = await read_image(image)

    # A spoken question takes priority over typed text
    if audio is not None:
        question = await run_in_threadpool(transcribe, await read_audio(audio), "audio/wav")
        if not question:
            return await not_heard_reply()

    return await build_reply(question.strip()[:500], image_bytes, image.content_type)


@app.post("/api/check-audio")
async def check_audio(
    audio: UploadFile = File(...),
    check_question: str = Form(...),   # the quiz question Ustad asked
    expected_answer: str = Form(...),  # the correct answer Ustad prepared
):
    """Spoken quiz answer: recording in -> 'correct or not' + spoken feedback out."""
    data = await read_audio(audio)
    child_answer = await run_in_threadpool(transcribe, data, "audio/wav")
    if not child_answer:
        return await not_heard_reply()
    return await build_feedback(check_question, expected_answer, child_answer)


@app.post("/api/check-text")
async def check_text(body: TextAnswer):
    """Typed quiz answer: text in -> 'correct or not' + spoken feedback out."""
    return await build_feedback(body.check_question, body.expected_answer, body.answer.strip())


# Serve the web page (public/index.html) at "/" when running on your PC.
# On Vercel, files in public/ are served directly by Vercel's CDN instead,
# so we only mount the folder if it exists. Must come last so it doesn't hide /api routes.
if os.path.isdir("public"):
    app.mount("/", StaticFiles(directory="public", html=True), name="public")