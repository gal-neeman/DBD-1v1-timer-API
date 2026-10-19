import logging
import time
from urllib.parse import urlsplit

from workers import Response, WorkerEntrypoint, fetch

from api.config import get_settings
from api.context import Context
from api.log import configure_logging
from api.responses import ApiResponse, json_error
from api.routing import resolve
from api.slugbot import SlugbotClient
from api.transport import HttpResponse

logger = logging.getLogger("dbd1v1timerapi")


def _to_worker_response(response: ApiResponse) -> Response:
    return Response(response.render(), status=response.status, headers=response.all_headers())


async def _workers_send(method: str, url: str, headers: dict[str, str]) -> HttpResponse:
    """HttpSend implementation over the Workers fetch API."""
    response = await fetch(url, method=method, headers=headers)
    return HttpResponse(response.status, await response.text())


def _client_info(request) -> dict[str, object]:
    """Who is calling: the useful subset of the invocation log, minus the client IP."""
    try:
        headers = request.headers
        cf = request.cf
        return {
            "user_agent": headers.get("user-agent"),
            "ray_id": headers.get("cf-ray"),
            "country": getattr(cf, "country", None),
            "asn": getattr(cf, "asn", None),
            "as_org": getattr(cf, "asOrganization", None),
        }
    except Exception:
        # Logging context must never fail the request.
        return {}


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
                ctx = Context(settings, SlugbotClient(settings, _workers_send))
                response = await handler(ctx, params)
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
                **_client_info(request),
            },
        )
        return _to_worker_response(response)
