FROM python:3.14-slim

WORKDIR /app

# install uv 
RUN pip install --no-cache-dir uv

# copy deps 
COPY pyproject.toml uv.lock README.md ./

# Install dependencies from the lock file
RUN uv sync --frozen --no-dev

# copy application 
COPY app ./app

# Use the virtual environment created by uv
ENV PATH="/app/.venv/bin:$PATH"

## cloud run listens on 8080

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
