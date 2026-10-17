# Start from a small official Python image
FROM python:3.12-slim

# Hugging Face Spaces runs containers as a normal user (id 1000), not root:
# safer, and required for some Space features
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1
WORKDIR $HOME/app

# Install libraries first: Docker caches this step, so code changes
# don't reinstall everything on every deploy
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Copy the rest of the project (the app/ and static/ folders)
COPY --chown=user . .

# Hugging Face Spaces expects the app on port 7860
EXPOSE 7860
# Use the port the hosting platform provides (PORT), or 7860 if none is set
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}