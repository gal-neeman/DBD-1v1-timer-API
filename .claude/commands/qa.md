---
description: Run every launch QA scenario from qa/qa-scenarios.html (unit harness + read-only staging) and report results
argument-hint: "[known=<player id>] [unranked=<player id>] [streak=<player id>] [inmatch=<player id>] [only=<IDs or area keys, comma-separated>]"
allowed-tools: Read, Grep, Glob, Write, Bash(npm test*), Bash(uv run python*), Bash(curl *), Bash(npx wrangler tail*), Bash(npx wrangler secret list*), Bash(npx wrangler deployments list*), Bash(git log*), Bash(git rev-parse*)
---

# Launch QA run

You are QA for this Worker's first prod launch. The scenario list lives in
[qa/qa-scenarios.html](../../qa/qa-scenarios.html), in the JSON block
`<script type="application/json" id="qa-scenarios">`. That block is the single source of truth.
Test **every** scenario in it (or only those matched by `only=`), and report on each one. Don't
skip a scenario because it looks covered by the unit tests. Don't invent scenarios that aren't in
the file. If you think one is missing, list it under "Suggested additions" in the report.

Arguments: `$ARGUMENTS`

- `known=`: KNOWN_PLAYER_ID, a Discord ID with ranked matches.
- `unranked=`: UNRANKED_ID, a valid Discord ID with no ranked data.
- `streak=`: STREAK_PLAYER_ID, a player on 10+ wins in a row (optional).
- `inmatch=`: IN_MATCH_ID, a player in a ranked match right now (optional).
- `only=`: comma-separated scenario IDs (`CCH-08`) or area keys (`STK`). Default: all.

If `known` is missing, ask for it once before the staging scenarios. If the user has no ID to
give, mark the scenarios that need it BLOCKED.

## Hard rules

1. **Never change anything deployed.** No `wrangler deploy`, `secret put/delete`, `rollback`,
   `versions upload` or dashboard changes. Only the read-only wrangler commands in `allowed-tools`.
2. **Never touch prod.** Every `prod`/`manual` scenario is BLOCKED (manual). Send no requests to
   `dbd1v1-api.truuehsoft.com`.
3. **Keep the repo clean.** Write harness scripts, captured output and the report only to the
   session scratchpad directory. Don't edit `src/`, `tests/` or the QA page. If a scenario's
   expected result looks wrong compared to the code, report it, don't fix it.
4. **No secrets in output.** Don't print the contents of `.dev.vars*`. For DEP-03, report only
   which keys exist and whether each value is empty or `changeme`.
5. **No assumed passes.** PASS needs evidence you actually observed (an assertion that ran, a
   status code, a log line). If you couldn't run it, it's BLOCKED with the reason.

## Steps

### 1. Load the scenarios

Parse the JSON block with a short `uv run python -I` script that reads the HTML file. Print the
count, then the IDs grouped by `agent` method. Apply `only=` if given.

`agent` tells you how to test each scenario. Values can be joined with `+`, which means do both
parts and PASS only if both pass.

| agent | How |
|-------|-----|
| `harness` | Python in the scratchpad driving the real code with the fakes from `tests/` |
| `staging` | `curl` against `stagingBaseUrl` plus `npx wrangler tail --env staging --format json` |
| `static` | Read `wrangler.jsonc` / repo files and check them |
| `manual` | Needs a human (dashboard, prod, Discord account, client app). BLOCKED (manual) |

Each scenario's `expected` items are the assertions. `setup`/`steps` say how to build it, and
`agentNotes` holds extra instructions for you. Follow them.

### 2. Baseline

Run TST-01 (`npm test`) first and record the pass count. Then run DEP-07: if staging's latest
deployment is older than `git log -1 --format=%cI`, put a warning at the top of the report that
staging results describe older code. Carry on anyway.

### 3. Harness scenarios

Build one scratchpad script per area (e.g. `qa_cfg.py`, `qa_stk.py`). Run them from the repo root
with `uv run python <script>`. Don't use `-I` here, because the script has to import `tests`.
Start each script with the two setup blocks from the page's "Unit-level harness" panel. Copy them
from the HTML so they match exactly. They give you:

- `call(slugbot, discord=None, cache=None, player_id=PLAYER_ID, **env)`: player details through
  the real handler, with env overrides via `make_env`.
- `run(method, path, **env)`: a full request through `entry.Default.fetch` with stubbed
  `workers` and `js` modules. Use it for config, routing and logging scenarios that involve
  the entrypoint.

Reuse what the repo already has. Don't reimplement it:

- `tests/test_handlers.py`: `FakeSlugbot`, `FakeDiscord`, `_match`, `_page`, `_wins`, `PLAYER_ID`, `OPPONENT_ID`
- `tests/fakes.py`: `MemoryCache` (`entries=`, `error=`, `.puts`)
- `tests/test_config.py`: `make_env(**overrides)` (`NAME=None` removes a var), `VALID_ENV`
- `tests/test_routing.py`: `make_context()` (its clients raise on any network call)
- `tests/slugbot/test_dtos.py`: `PLAYER_JSON`, `MATCH_BATCH_JSON`. `tests/discord/test_dtos.py`: `USER_JSON`
- `api.routing.resolve`, `api.config.Settings` / `get_settings` / `_cached_settings`, `api.log.JsonFormatter`

Techniques:

- **Capture logs** with a handler that keeps `JsonFormatter` output in a list, and assert on
  `msg`, `level` and the extra fields. Check that a line is absent as carefully as you check that
  one is present (e.g. no `Discord user lookups` on a full cache hit).
- **Timeouts**: a send that does `await asyncio.sleep(3)`, with the timeout var set to `"1"`.
  Measure the elapsed time.
- **Custom upstream bodies**: write a small async `send(method, url, headers)` returning
  `api.transport.HttpResponse(status, body_text)`, for non-JSON bodies, header capture, or
  parallelism checks.
- **Cache failures**: a class with async `get`/`put` that raise.
- **`_WorkersCache` (CCH-07)**: replace `sys.modules["js"].caches` with a fake whose `open()`
  returns an object with async `match`/`put`.
- Reset `config._cached_settings = None` before each settings-dependent run.

Run each scenario in its own `try`, so one failure doesn't hide the rest. Print one result line
per scenario: `ID | PASS/FAIL | evidence`.

### 4. Staging scenarios

Base URL: `https://dbd1v1-api-staging.truuehsoft.com`.

1. Start `npx wrangler tail --env staging --format json` in the background, writing to a
   scratchpad file. Give it a few seconds to connect before sending requests.
2. Use `curl -sS -i` so you have status, headers and body. Save each response to the scratchpad.
3. Match tail events to requests by path and time. The Worker's JSON log lines are the
   `message` entries inside each event's `logs` array.
4. **Run the cache scenarios in order:** DSC-06 needs a cold cache, so run it first or wait 65 s
   after any earlier request for that player. Then CCH-08 (repeat within 30 s), then CCH-09
   (wait 65 s, then repeat). To wait, use Monitor with an until-loop or a background
   `sleep 65`, never a foreground sleep.
5. A single unrelated tail glitch (e.g. a disconnect) isn't a FAIL. Retry once, and if it still
   fails, mark the log part BLOCKED with the reason.
6. Stop the tail when you're done.

### 5. Static scenarios

Parse `wrangler.jsonc` with Python after stripping `//` and `/* */` comments, and check what the
scenario asks for. For DEP-03, check `.dev.vars.prod` key names and value emptiness only.

### 6. Report

Write `qa-report-<YYYY-MM-DD-HHMM>.md` to the scratchpad. Structure:

1. **Header**: commit (`git rev-parse --short HEAD`), staging deployment time and whether it
   matches HEAD, arguments used, totals (PASS / FAIL / BLOCKED).
2. **Failures first**: for each FAIL, give the scenario ID and title, the expected item that
   failed, what you actually saw (status, body excerpt, log line), and the most likely code
   location as a `src/...:line` reference. Mark whether it's a launch blocker (wrong status
   code, 500, data wrong, secret leak) or minor.
3. **All results**: one table, `| ID | Title | Method | Result | Evidence |`, in the page's order.
   Keep evidence to one line, e.g. `502 upstream_error; WARNING "Slugbot error status" 500`.
4. **Blocked**: what a human needs to do for each one. For `manual` scenarios, point to the card
   with `qa/qa-scenarios.html#<ID>`.
5. **Suggested additions**: scenarios you think are missing, if any.

Then, in your reply: print the report path, the totals, and the failures with one line each.
Don't paste the whole table. If there are any failures, offer to publish the report as a page
for sharing. End by reminding the user that `manual` scenarios still need a human, and that
they can record their own marks on the QA page.
