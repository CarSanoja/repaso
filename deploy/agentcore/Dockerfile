FROM --platform=linux/arm64 python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md LICENSE requirements.lock ./
COPY src ./src

RUN pip install --no-cache-dir setuptools==80.9.0 && pip install --no-build-isolation --no-cache-dir -c requirements.lock ".[runtime]"

EXPOSE 8080

ENTRYPOINT ["python", "-m", "repaso.runtime.app"]
