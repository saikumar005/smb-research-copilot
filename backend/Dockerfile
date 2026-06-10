FROM python:3.12-slim

# Install system dependencies (needed for compiling psycopg2 and general building)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy uv binary from the official uv image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Copy dependency specifications
COPY pyproject.toml ./

# Install dependencies directly into the system python site-packages (no virtualenv needed inside Docker container)
RUN uv pip install --system -r pyproject.toml

# Copy the application source code
COPY . .

# Expose FastAPI's default port
EXPOSE 8000

# Start Uvicorn with auto-reload for development
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
