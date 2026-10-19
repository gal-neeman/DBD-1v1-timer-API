# DBD-1v1-timer-API
An API built to support integration with third party services, specifically now for DBDLeague's 1v1 leaderboard API.

Runs as a Cloudflare Python Worker with no runtime dependencies (stdlib only).

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/status` | Public client config (poll intervals, versions, status message) |
| GET | `/api/v1/players/{playerId}` | Player stats from Slugbot: display name, season winrate (%), current win streak, rank, points and the last 10 match results (`1` win / `0` loss, newest first). `404` if Slugbot has no data for the player, `502`/`503` if Slugbot errors or is unreachable |

All responses are JSON with camelCase fields. Errors use `{"error": {"code": "...", "message": "..."}}`.

## Configuration

[wrangler.jsonc](wrangler.jsonc) has two config blocks: the top level (prod, also used by `npm run dev`) and `env.staging`.

- **Public vars** live in `vars` and are committed with their real values. Environments do **not** inherit `vars` from the top level, so a new variable must be added to both blocks.
- **Secrets** (`SLUGBOT_API_KEY`) are declared under `secrets.required` in each block:
  - Local: `cp .dev.vars.example .dev.vars` and fill in values (`.dev.vars*` is gitignored). Optionally add `.dev.vars.staging` for `dev:staging`.
  - Deployed: set per environment. Deploys fail if a required secret is missing.
    ```
    npx wrangler secret put SLUGBOT_API_KEY                # prod
    npx wrangler secret put SLUGBOT_API_KEY --env staging
    ```

## Development

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/) and Node.js.

```
uv sync
npm install
npm run dev            # local run with the prod (top-level) config -> http://localhost:8787
npm run dev:staging    # local run with the staging config
```

Run the unit tests (no Workers runtime needed):

```
# bash / zsh
PYTHONPATH=src uv run python -m unittest discover -s tests -t .

# PowerShell
$env:PYTHONPATH = 'src'; uv run python -m unittest discover -s tests -t .
```

## Deploy

| Environment | Command | Worker | URL |
|-------------|---------|--------|-----|
| staging | `npm run deploy:staging` | `dbd1v1timerapi-staging` | https://dbd1v1-api-staging.truuehsoft.com |
| prod | `npm run deploy:prod` | `dbd1v1timerapi` | https://dbd1v1-api.truuehsoft.com |

Both are served only on their custom domain (`workers_dev` and `preview_urls` are off). Prod is the top-level config, so a bare `wrangler deploy` deploys to **prod**.

First deploy of an environment:

1. `truuehsoft.com` must be an active zone in the same Cloudflare account.
2. Neither hostname may have an existing CNAME record (Cloudflare creates the DNS record and certificate on deploy).
3. The required-secret check fails a deploy to a Worker that has no secrets yet, so upload them with the first deploy:
   ```
   npm run deploy:staging -- --secrets-file .dev.vars.staging
   npm run deploy:prod -- --secrets-file .dev.vars.prod
   ```
   Later deploys keep existing secrets. To change one, run `npx wrangler secret put SLUGBOT_API_KEY` (add `--env staging` for staging).

## Layout

```
src/entry.py          Worker entrypoint; the only module that imports `workers`
src/api/              routing, handlers, response DTOs, config, logging
src/api/transport.py  HttpSend interface for outbound HTTP (implemented over `workers.fetch` in entry.py)
src/api/slugbot/      Slugbot client, endpoint registry (endpoints.py) and response DTOs
```

Handlers receive a `Context` (settings + `SlugbotClient`). New Slugbot endpoints are added to `SlugbotEndpoint` in [src/api/slugbot/endpoints.py](src/api/slugbot/endpoints.py), then exposed as a method on `SlugbotClient`.

## Logging

Logs are written as one JSON object per line to stdout through the stdlib `logging` module ([src/api/log.py](src/api/log.py)). Every request emits an access line with `method`, `path`, `status` and `duration_ms`. Workers Logs (enabled through `observability`) indexes these fields. Set the level with the `LOG_LEVEL` var.
