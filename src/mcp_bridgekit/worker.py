from rq import Worker, Queue
from redis import Redis
import structlog
from .config import settings

logger = structlog.get_logger()

def process_job(request_dict: dict, job_id: str):
    logger.info("processing background job", job_id=job_id)
    # TODO: run MCP call and store result in Redis for polling/SSE
    print(f"[Worker] Completed job {job_id}")

def main():
    redis = Redis.from_url(settings.redis_url)
    worker = Worker(["default"], connection=redis)
    worker.work()

if __name__ == "__main__":
    main()
