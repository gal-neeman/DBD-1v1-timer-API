import logging
import time
from urllib.parse import urlsplit

from workers import Response, WorkerEntrypoint

from api.config import get_settings
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
            # Install the JSON handler before parsing, so config warnings are formatted too.
            configure_logging()
            settings = get_settings(self.env)
            configure_logging(settings.log_level)
            resolved = resolve(method, path)
            if isinstance(resolved, ApiResponse):
                response = resolved
            else:
                handler, params = resolved
                response = await handler(settings, params)
        except Exception as exc:
            configure_logging()
            reason = f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__
            logger.exception(
                "Unhandled error", extra={"method": method, "path": path, "reason": reason}
            )
            response = json_error(500, "internal_error", "Internal server error")

        logger.info(
            path,
            extra={
                "method": method,
                "path": path,
                "status": response.status,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            },
        )
        return _to_worker_response(response)
