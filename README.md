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

[wrangler.jsonc](wrangler.jsonc) has three config blocks: the top level (local dev only), `env.staging` and `env.prod`.

- **Public vars** live in `vars` and are committed with their real values. Environments do **not** inherit `vars` from the top level, so a new variable must be added to all three blocks.
- **Secrets** (`SLUGBOT_API_KEY`) are declared under `secrets.required` in each block:
  - Local: `cp .dev.vars.example .dev.vars` and fill in values (`.dev.vars*` is gitignored). Optionally add `.dev.vars.staging` / `.dev.vars.prod` for `dev:staging` / `dev:prod`.
  - Deployed: set per environment. Deploys fail if a required secret is missing.
    ```
    npx wrangler secret put SLUGBOT_API_KEY --env staging
    npx wrangler secret put SLUGBOT_API_KEY --env prod
    ```

## Development

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/) and Node.js.

```
uv sync
npm install
npm run dev            # top-level config -> http://localhost:8787
npm run dev:staging    # local run with the staging config
npm run dev:prod       # local run with the prod config
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
| prod | `npm run deploy:prod` | `dbd1v1timerapi-prod` | https://dbd1v1-api-prod.truuehsoft.com |

Both are served only on their custom domain (`workers_dev` and `preview_urls` are off). Always deploy with an environment; the top-level config is for local dev.

First deploy of an environment:

1. `truuehsoft.com` must be an active zone in the same Cloudflare account.
2. Neither hostname may have an existing CNAME record (Cloudflare creates the DNS record and certificate on deploy).
3. The required-secret check fails a deploy to a Worker that has no secrets yet, so upload them with the first deploy:
   ```
   npm run deploy:staging -- --secrets-file .dev.vars.staging
   ```
   Later deploys keep existing secrets. To change one, run `npx wrangler secret put SLUGBOT_API_KEY --env <env>`.

## Logging

Logs are written as one JSON object per line to stdout through the stdlib `logging` module ([src/api/log.py](src/api/log.py)). Every request emits an access line with `method`, `path`, `status` and `duration_ms`. Workers Logs (enabled through `observability`) indexes these fields. Set the level with the `LOG_LEVEL` var.
