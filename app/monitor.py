import time

metrics = {
    "requests": 0,
    "errors": 0,
    "total_time": 0
}

def track_request(start_time, success=True):
    metrics["requests"] += 1
    metrics["total_time"] += (time.time() - start_time)

    if not success:
        metrics["errors"] += 1