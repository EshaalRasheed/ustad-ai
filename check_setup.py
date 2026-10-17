"""Checks that Gemini (chat + embeddings) and Supabase are connected."""
from google import genai
from google.genai import types
from supabase import create_client

from app import config

# ---- 1. Gemini chat: can it answer simply in Urdu? ----
client = genai.Client(api_key=config.GEMINI_API_KEY)
reply = client.models.generate_content(
    model=config.CHAT_MODEL,
    contents="Explain photosynthesis to a 10-year-old in 2 short, simple Urdu sentences.",
)
print("Gemini chat reply:\n", reply.text, "\n")

# ---- 2. Gemini embeddings: does it return 768 numbers? ----
result = client.models.embed_content(
    model=config.EMBED_MODEL,
    contents="پودے سورج کی روشنی سے اپنی خوراک بناتے ہیں",  # "Plants make their food from sunlight"
    config=types.EmbedContentConfig(output_dimensionality=config.EMBED_DIM),
)
print("Embedding length:", len(result.embeddings[0].values), "(should be 768)\n")

# ---- 3. Supabase: can we reach the textbook table? ----
db = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
rows = db.table("textbook_chunks").select("id").limit(1).execute()
print("Supabase connected. Rows currently in table:", len(rows.data))