import time
import uuid
from collections import deque

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from prometheus_client import Counter, CONTENT_TYPE_LATEST, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware

EMAIL = "23f3000863@ds.study.iitm.ac.in"  # <-- replace if this isn't your logged-in email
START_TIME = time.time()

app = FastAPI()

# ---- Prometheus counter ----------------------------------------------------
REQUEST_COUNTER = Counter(
    "http_requests_total",
    "Total number of HTTP requests received",
    ["method", "path"],
)

# ---- In-memory structured log ring buffer ---------------------------------
LOG_BUFFER = deque(maxlen=2000)


def log_event(level: str, path: str, request_id: str, **extra):
    entry = {
        "level": level,
        "ts": time.time(),
        "path": path,
        "request_id": request_id,
    }
    entry.update(extra)
    LOG_BUFFER.append(entry)


class ObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        path = request.url.path

        REQUEST_COUNTER.labels(method=request.method, path=path).inc()

        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start

        log_event(
            "info",
            path,
            request_id,
            method=request.method,
            status_code=response.status_code,
            duration_s=duration,
        )

        response.headers["X-Request-ID"] = request_id
        return response


app.add_middleware(ObservabilityMiddleware)


@app.get("/work")
async def work(n: int = 1):
    # Do K units of "work" (busy loop stand-in).
    total = 0
    for i in range(max(n, 0)):
        total += i
    return {"email": EMAIL, "done": n}


@app.get("/metrics")
async def metrics():
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "uptime_s": time.time() - START_TIME}


@app.get("/logs/tail")
async def logs_tail(limit: int = 20):
    limit = max(1, min(limit, len(LOG_BUFFER))) if LOG_BUFFER else 0
    return list(LOG_BUFFER)[-limit:] if limit else []


@app.get("/")
async def root():
    return {"status": "ok", "service": "observability-api"}
