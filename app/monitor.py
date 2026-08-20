import time
from collections import Counter

metrics = {
    "requests": 0,
    "errors": 0,
    "total_time": 0.0,
    "by_status": Counter(),
    "by_route": Counter(),
}


def track_request(start_time, status_code, route):
    """Record one request. `route` is the route template, not the raw path, so
    /appointments/1 and /appointments/2 count as the same endpoint instead of
    growing the counter by one key per appointment."""
    metrics["requests"] += 1
    metrics["total_time"] += time.time() - start_time
    metrics["by_status"][str(status_code)] += 1
    metrics["by_route"][route] += 1

    if status_code >= 400:
        metrics["errors"] += 1
