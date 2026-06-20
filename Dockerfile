FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY stashai ./stashai

RUN pip install --no-cache-dir .

RUN mkdir -p /app/data /app/models \
    && useradd --create-home --shell /usr/sbin/nologin stashai \
    && chown -R stashai:stashai /app

USER stashai

EXPOSE 8088

VOLUME ["/app/data", "/app/models"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8088/api/overview', timeout=3).read()" || exit 1

CMD ["uvicorn", "stashai.web.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8088"]
