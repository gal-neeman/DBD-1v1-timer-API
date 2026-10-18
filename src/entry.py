import logging
import time
from urllib.parse import urlsplit

from workers import Response, WorkerEntrypoint

from api.config import Settings
from api.log import configure_logging
from api.responses import ApiResponse, json_error
from api.routing import resolve

logger = logging.getLogger("dbd1v1timerapi")


def _to_worker_response(response: ApiResponse) -> Response:
    return Response(response.render(), status=response.status, headers=response.all_headers())


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        # Workers freeze the clock during execution and only advance it on I/O,
        # so duration_ms reads 0 for requests that never await I/O.
        started = time.perf_counter()
        method = request.method
        path = urlsplit(request.url).path
        try:
            settings = Settings.from_env(self.env)
            configure_logging(settings.log_level)
            resolved = resolve(method, path)
            if isinstance(resolved, ApiResponse):
                response = resolved
            else:
                handler, params = resolved
                response = await handler(settings, params)
        except Exception:
            configure_logging()
            logger.exception("Unhandled error", extra={"method": method, "path": path})
            response = json_error(500, "internal_error", "Internal server error")

        logger.info(
            "request",
            extra={
                "method": method,
                "path": path,
                "status": response.status,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            },
        )
        return _to_worker_response(response)
