"""Central settings: reads keys and model names from the .env file."""
import os

from dotenv import load_dotenv

# Load the variables from .env into the environment
load_dotenv()

# API keys and connection details
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Model routing: a stronger model for explaining, a lighter one for simple jobs.
# Each Gemini model has its OWN free daily quota, so splitting work saves quota.
CHAT_MODEL = os.getenv("CHAT_MODEL", "gemini-3.8-flash")   # explains answers
FAST_MODEL = os.getenv("FAST_MODEL", CHAT_MODEL)            # transcribes + checks answers

EMBED_MODEL = os.getenv("EMBED_MODEL", "gemini-embedding-001")
EMBED_DIM = int(os.getenv("EMBED_DIM", "768"))  # must match vector(768) in the database