# DBD-1v1-timer-API
An API built to support integration with third party services, specifically now for DBDLeague's 1v1 leaderboard API.

Runs as a Cloudflare Python Worker with no runtime dependencies (stdlib only).

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/status` | Public client config (poll intervals, versions, status message) |
| GET | `/api/v1/player/{playerId}/details` | Player stats (currently a static placeholder; Slugbot integration TODO) |

All responses are JSON with camelCase fields. Errors use `{"error": {"code": "...", "message": "..."}}`.

## Configuration

- **Public vars** live in `vars` in [wrangler.jsonc](wrangler.jsonc) and are committed with their real values.
- **Secrets** (`SLUGBOT_API_KEY`) are declared under `secrets.required` in `wrangler.jsonc`:
  - Local: `cp .dev.vars.example .dev.vars` and fill in values (`.dev.vars` is gitignored).
  - Production: `npx wrangler secret put SLUGBOT_API_KEY`. Deploys fail if a required secret is missing.

## Development

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/) and Node.js.

```
uv sync
npm install
npm run dev        # uv run pywrangler dev -> http://localhost:8787
```

Run the unit tests (no Workers runtime needed):

```
# bash / zsh
PYTHONPATH=src uv run python -m unittest discover -s tests -t .

# PowerShell
$env:PYTHONPATH = 'src'; uv run python -m unittest discover -s tests -t .
```

## Deploy

```
npm run deploy     # uv run pywrangler deploy
```

## Logging

Logs are written as one JSON object per line to stdout through the stdlib `logging` module ([src/api/log.py](src/api/log.py)). Every request emits an access line with `method`, `path`, `status` and `duration_ms`. Workers Logs (enabled through `observability`) indexes these fields. Set the level with the `LOG_LEVEL` var.
