FROM python:3.12-slim

WORKDIR /app
COPY . /app
RUN pip install -e .

EXPOSE 8000
CMD ["uvicorn", "mcp_bridgekit.app:app", "--host", "0.0.0.0", "--port", "8000"]
