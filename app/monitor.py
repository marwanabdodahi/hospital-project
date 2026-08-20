import time
from collections import Counter

metrics = {
    "requests": 0,
    "errors": 0,
    "total_time": 0.0,
    "by_status": Counter(),
    "by_path": Counter(),
}


def track_request(start_time, status_code, path):
    metrics["requests"] += 1
    metrics["total_time"] += time.time() - start_time
    metrics["by_status"][str(status_code)] += 1
    metrics["by_path"][path] += 1

    if status_code >= 400:
        metrics["errors"] += 1
