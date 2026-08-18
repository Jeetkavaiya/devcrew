FROM python:3.12-slim

WORKDIR /app

# Install dependencies first so this layer is cached across code changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the actual package. src/devcrew/... becomes /app/src/devcrew/...
COPY src/ ./src/

# No packaging file (no pyproject.toml/setup.py) exists in this project,
# so "devcrew" is made importable the same way it presumably is locally:
# by putting src/ on PYTHONPATH rather than pip-installing the package.
ENV PYTHONPATH=/app/src

# GROQ_API_KEY, DEVCREW_MODEL, DEVCREW_REQUEST_DELAY etc. are read from
# the environment at runtime (see llm.py's load_dotenv() + os.environ
# calls) — pass them in with `docker run -e` or `--env-file .env`,
# never bake secrets into the image.

EXPOSE 8000

CMD ["uvicorn", "devcrew.api:app", "--host", "0.0.0.0", "--port", "8000"]