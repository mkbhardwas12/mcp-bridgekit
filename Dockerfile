FROM python:3.12-slim

WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir -e . gunicorn uvicorn[standard]

ENV WEB_CONCURRENCY=4
EXPOSE 8000

# gunicorn with uvicorn workers — 4 processes, each with its own event loop
CMD ["gunicorn", "mcp_bridgekit.app:app", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "4", \
     "--timeout", "120", \
     "--graceful-timeout", "30"]
