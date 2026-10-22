import logging
import time
from urllib.parse import quote, urlsplit

from js import caches
from workers import Response, WorkerEntrypoint, fetch

from api.config import get_settings
from api.context import Context
from api.discord import DiscordClient
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


class _WorkersCache:
    """Cache implementation over a named Workers Cache API cache (caches.open).

    A named cache keeps our entries apart from the zone's CDN cache (caches.default), and
    each environment configures its own name. Entries live in the data center that wrote
    them only, and the API is a no-op outside custom domains (e.g. dashboard previews),
    which just means every get misses.
    """

    def __init__(self, name: str, origin: str) -> None:
        self._name = name
        self._cache = None
        # The Cache API keys by URL, so keys become synthetic URLs on our own origin.
        # Bump the version to drop every entry if the stored format changes.
        self._prefix = f"{origin}/__cache/v1/"

    def _url(self, key: str) -> str:
        return self._prefix + quote(key, safe="/")

    async def _open(self):
        # Opened on first use, so requests that never touch the cache don't pay for it.
        if self._cache is None:
            self._cache = await caches.open(self._name)
        return self._cache

    async def get(self, key: str) -> str | None:
        response = await (await self._open()).match(self._url(key))
        if response is None:
            return None
        return await response.text()

    async def put(self, key: str, value: str, ttl_sec: int) -> None:
        response = Response(
            value,
            headers={"Content-Type": "text/plain", "Cache-Control": f"max-age={ttl_sec}"},
        )
        await (await self._open()).put(self._url(key), response.js_object)


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
        url = urlsplit(request.url)
        path = url.path
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
                ctx = Context(
                    settings,
                    SlugbotClient(settings, _workers_send),
                    DiscordClient(settings, _workers_send),
                    _WorkersCache(settings.cache_name, f"{url.scheme}://{url.netloc}"),
                )
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
