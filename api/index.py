"""Vercel entry point: Vercel runs Python files in the api/ folder as serverless functions.

We simply import the FastAPI app we already built, so the same code runs
on your PC (uvicorn) and on Vercel.
"""
from app.main import app  # noqa: F401  (Vercel looks for a variable named "app")