# Using a separate build file so we can turn this into a docker image later
FROM python:3.12-slim
# COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Python package is managed through UV
RUN pip install uv

WORKDIR /app

COPY ./app/pyproject.toml ./app/uv.lock ./

# Install dependencies using uv
RUN uv sync --frozen --active

COPY ./app/src ./src
COPY ./app/logs ./logs

EXPOSE 8000

RUN pwd

# Debug testing env, if true then we are running a test

# Run with uvicorn
# !Important! must change the directory to the where the .venv is located
# else it cant find uvicorn
CMD ["uv", "run", "--active", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Health check for the image
HEALTHCHECK --interval=30s --timeout=30s --start-period=30s --retries=5 \
  CMD [ "curl -f http://localhost:8000" || exit 1]