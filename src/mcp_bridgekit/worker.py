import json
from rq import Worker, Queue
from redis import Redis
from mcp_bridgekit.core import BridgeKit, BridgeRequest

redis = Redis.from_url("redis://localhost:6379")
queue = Queue(connection=redis)
bridge = BridgeKit()

def process_job(request_dict: dict, job_id: str):
    """Background worker that runs long MCP calls"""
    request = BridgeRequest(**request_dict)
    # Re-run the call synchronously in worker
    # In real: stream result to Redis pub/sub or webhook
    print(f"[Worker] Processing job {job_id} for user {request.user_id}")
    # TODO: store result in Redis for frontend polling/SSE

def main():
    worker = Worker([queue], connection=redis)
    worker.work()

if __name__ == "__main__":
    main()
