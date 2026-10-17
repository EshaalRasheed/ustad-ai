"""Full voice test: speak a question -> Ustad answers out loud in Urdu."""
import io
import os

import sounddevice as sd
import soundfile as sf

from app.tutor import ask_ustad
from app.voice import speak, transcribe

SAMPLE_RATE = 16000  # 16 kHz is standard quality for speech
SECONDS = 6          # how long to record

# ---- 1. Record the child's question from the microphone ----
input(f"Press Enter, then ask your question (you have {SECONDS} seconds)...")
print("Recording... speak now!")
recording = sd.rec(int(SECONDS * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1)
sd.wait()  # wait until recording finishes
print("Recording finished.\n")

# Convert the recording into WAV file bytes (kept in memory, not saved to disk)
buffer = io.BytesIO()
sf.write(buffer, recording, SAMPLE_RATE, format="WAV")
audio_bytes = buffer.getvalue()

# ---- 2. Speech-to-text ----
question = transcribe(audio_bytes, mime_type="audio/wav")
print("You asked:", question or "(nothing heard)")
if not question:
    raise SystemExit("No speech detected. Speak closer to the microphone and try again.")

# ---- 3. Ustad thinks: understand -> explain ----
result = ask_ustad(question)
print(f"[Subject: {result['subject']} | Safe: {result['safe']}]")
print("Ustad:", result["explanation_urdu"])
print("Question for you:", result["check_question_urdu"], "\n")

# ---- 4. Text-to-speech: explanation, then the check question ----
spoken_text = result["explanation_urdu"] + " " + result["check_question_urdu"]
answer_audio = speak(spoken_text)

with open("answer.mp3", "wb") as f:
    f.write(answer_audio)
print("Saved Ustad's spoken answer to answer.mp3 - playing it now...")

# Open the MP3 with your default audio player (Windows)
os.startfile("answer.mp3")