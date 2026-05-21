# ExaCheck Changelog

## TBA - 0.2.0

Features:

- Health checks now honour the `metric_down` configuration option. When a check has `metric_down` set and the service falls, the routes are no longer fully withdrawn — they are instead re-advertised at the configured down metric. When the service recovers, the routes are re-announced at the normal metric. The recovery still requires `rise` consecutive successes, and a disable file or daemon shutdown still fully withdraws the routes. A new `current_metric` field on the internal check state tracks what metric is on the wire.
- Configuration reload no longer restarts a worker for cosmetic edits. Changes to a check are now classified: operational fields (`args`, `interval`, `rise`, `fall`, `disable`) still trigger a full worker restart, route-attribute fields (`prefixes`, `nexthop`, `metric`, `metric_down`, `communities`, `as_path`, `local_preference`, `path_id`, `neighbors`) are pushed to the running worker over a `multiprocessing.Queue` for an in-place re-announce — preserving rise/fall counters and avoiding the brief route withdrawal/BGP churn the previous code caused. Pure cosmetic edits (e.g. `description`) are now a no-op.
- `SIGHUP` now triggers an immediate configuration reload (previously operators had to wait up to one `monitoring_interval` for the file polling loop to notice the change).
- The reload now logs a warning when top-level fields that the master only reads at startup — `exacheck` (monitoring_interval / live_reload), `logging`, `sentry` — are modified, so operators know those changes will not take effect until ExaCheck is restarted.

Fixes:

- `Announcer.send_command` no longer interpolates the literal string `"None"` into ExaBGP commands when a check has `metric_down` set but no normal `metric`. The empty metric token is now elided and intervening whitespace collapsed.
- Configuration change detection now uses a SHA-256 content hash rather than the file's mtime. `touch`ing the file no longer triggers a spurious reload, and a fix to a previously-broken file is reliably detected even if mtime is preserved. After a failed reload the hash is updated to the broken bytes so the reload is not retried until the file actually changes again.
- Worker `SIGINT`/`SIGTERM` handlers no longer perform I/O (stdout writes via the Announcer, logger lock acquisitions). The handler now only sets a flag; the main loop notices it at the top of the next iteration and performs the route withdrawal and exit from a normal execution context. Removes a latent deadlock risk if a signal arrived while the worker was holding the Loguru lock.

Internal:

- `Worker.__init__` no longer calls `run()`; the multiprocessing target is now the module-level `worker_main(check, notifications, queue)` wrapper that constructs a `Worker` and invokes `run()`. Tests can now instantiate a `Worker` directly for inspection instead of bypassing `__init__` with `__new__`.
- Internal-only worker methods (`success`/`failure`/`announce`/`degrade`/`withdraw`/`cleanup`) renamed with a leading underscore. `Worker`'s public surface is now just `__init__` and `run`.
- `Worker.method` property replaced with the plain `_build_method()` method, making it clear that each call allocates a new check-method instance. It is now invoked exactly once, when `run` builds the `CheckExecutor`.

## TBA - 0.1.7

Fixes:

- Worker child processes are no longer left as zombies when ExaBGP terminates ExaCheck. The previous SIGCHLD-based reaper raced against shutdown and respawned workers as the master was exiting; it has been removed in favour of an explicit terminate-and-join in the master cleanup handler, with a SIGKILL escalation on hang. The same fix is applied to `_stop_worker` so live-reload removals do not leak zombies either.
- Shell health check output is no longer dropped — and, more importantly, no longer leaks into the ExaBGP command stream. `subprocess.run` is now invoked with `capture_output=True`, so `stdout`/`stderr` are properly captured into the `CheckResult` instead of being inherited from the parent (whose stdout is the ExaBGP control channel).
- ICMP health check: the `Packets lost (...)` error string reported the boolean result of the comparison instead of the actual number of lost packets, due to walrus-operator precedence. Now reports the correct count.
- ICMP health check: the "max jitter exceeded" error message reported `max_rtt` instead of `jitter`. Now reports the jitter value.
- DNS resolution error handling: the `getaddrinfo` errno was being matched against string literals (`"-9"`, `"-2"`), so the branches never fired and `AddressFamilyError` was effectively unreachable. Now matched against the `socket.EAI_*` integer constants.
- `CheckResult.date` was evaluated once at module import time, so every check result shared the same timestamp. Switched to `default_factory=datetime.now` so each result is dated when it is created.
- `Notifications.notify` no longer raises `IndexError` on an unknown event type; it now falls back to the `INFO` notification level.
- `_stop_worker` no longer raises `IndexError` if the named worker is missing from the job list; it logs an error and returns.
- `Sleeper` no longer enforces a hard-coded 1-second floor on the sleep interval — health checks with sub-second intervals now run at the configured cadence. If an iteration over-runs the interval, the next iteration runs immediately (with a warning) instead of being delayed to a full second.

Misc:

- Bump ExaBGP requirement to `^5.0.9` (was `^4.2.25`)
- Bump tabulate to `^0.10.0`
- Narrow supported Python range to `>=3.11,<3.14` (ExaBGP 5 does not support Python 3.14)
- Refresh all other core and development dependencies to their latest compatible versions
- Drop the obsolete "Known Issues" note about the ExaBGP 4.2 `six.moves` vendoring issue on Python 3.12 (no longer applicable on ExaBGP 5)
- Master monitoring loop simplified: the redundant `kill(pid, 0)` liveness check has been removed; `Process.is_alive()` is sufficient and already reaps exited children
- `Settings` duplicate log-path detection rewritten using `collections.Counter` (functionally identical, no longer relies on `set.add` returning `None` inside a comprehension)

## 2025-03-17 - 0.1.6

Fixes:

- Allow setting `expected_status` for the HTTP method as a single integer (previously only a list of integers was allowed)

Misc:

- Update core requirements:
  - Apprise
  - Loguru
  - Pydantic
  - httpx
  - click
  - Sentry
  - ExaBGP
- Update various development dependencies
- Minimum Python release 3.11 due to ipython dependency for dev

## 2024-10-28 - 0.1.5

Misc:

- Update Sentry requirement
- Update various development dependencies
- Support Python 3.13
  - Docker image is now built using Python 3.13 base by default
  - Development environment is now using Python 3.13 by default

## 2024-09-10 - 0.1.4

Misc:

- Remove deprecated `version` keyword from dev container compose file
- Add comments to example compose file
- Update various development dependencies
- Add respx to test dependencies
- Minor formatting fixes
- Update core requirements:
  - Apprise
  - Sentry
  - httpx
  - Pydantic

## 2024-07-10 - 0.1.3

Fixes:

- If a DNS health check had a response pattern configured the last character of the response was being removed during validation. Some additional debug output was added in case of future issues.

Misc:

- Update core requirements:
  - Sentry
  - Pydantic
- Update various development dependencies (linting/formatting tools)
- Add debugger launch configs for VS Code

## 2024-06-13 - 0.1.2

Changes:

- Bump ExaBGP to build 4.2.22 - This fixes build issues on Python 3.12 which required working around. The Docker image has had the manual deployment of ExaBGP removed since it can now be built on its own successfully.

Misc:

- Update core requirements:
  - Pydantic
  - Sentry
  - Apprise
  - ujson
- Update various development dependencies (linting/formatting tools)
- VS Code Workspace fixes (debugpy, spelling)
- Dev container image mirror changed to `gitlab.com`
- Remove duplicate apt install in dev container
- Reformat docker ignore file
- Update default compose file

## 2024-04-18 - 0.1.1

Changes:

- Docker builds now use a venv rather than installing in system Python
- Docker builds now use Python 3.12 as the base

Fixes:

- Docker builds were not including ExaBGP so they would not be able to work. To fix this the requirement on ExaBGP has been dropped from Python >= 3.12. To use ExaCheck with Python 3.12 onwards (if not using Docker) you must currently install ExaBGP from source:

```bash
python3 -m pip --no-cache-dir install "git+https://github.com/Exa-Networks/exabgp.git@4.2"
```

Misc:

- Update Apprise, Pydantic, Sentry and various development related modules

## 2024-04-01 - 0.1.0

Changes:

- The HTTP health check method now uses [HTTPX](https://www.python-httpx.org/) instead of `requests` to make the request
- HTTP check SNI adapter removed - HTTPX can handle SNI natively without requiring an adapter

Misc:

- Update Sentry, Apprise and Pydantic releases
- Update development group dependency Markdown
- Update various development dependencies
- Pytest configuration moved from .ini file to `pyproject.toml`
- MyPy configuration moved from .ini file to `pyproject.toml`

Features

- With the change to [HTTPX](https://www.python-httpx.org/), the HTTP health check now supports HTTP2 (defaults to `False`)

## 2024-02-21 - 0.0.11

Fixes:

- Reap zombie processes and respawn on failure (fixes [#8](https://github.com/exacheck/exacheck/issues/8))

Misc:

- Update Sentry and dnspython releases

## 2024-02-08 - 0.0.10

Changes:

- Add support for Python 3.10 and Python 3.12
  - ExaBGP will be built from source if using Python 3.12 (using the 4.2 branch)
- Dockerfile changes to add support for Python 3.12:
  - Install ExaCheck from git rather than PyPi to allow easier version customisation
  - Make sure wheel/setuptools/pip is up to date

Misc:

- Update Semgrep and pydantic releases
- Remove requirement on types-requests; this is not needed for production usage
- Re-format pyproject.toml - use groups for development/typing/formatting/testing

## 2024-02-07 - 0.0.9

Fixes:

- `http` check method fails to parse the URL correctly for IPv6 hosts; IPv6 address must be enclosed with `[]`

## 2024-02-07 - 0.0.8

Fixes:

- Log file `count` option was not being used at all; log files would rotate but never be cleaned up
- If a `host` value was provided for the `http` check method the value was being ignored; the host was overwritten from the hostname in URL

## 2024-01-31 - 0.0.7

Fixes:

- Correct the logging event types for announce/withdraw of routes for log filtering to work correctly
- Fix metric attribute naming error

Changes:

- Log exceptions when sending routes to ExaBGP
- Update syslog format string
  - Include hostname when logging to remote servers
  - Include timestamp when logging to remote servers or when structured logging is used

Features:

- Add the following options for Sentry; values are set to the Sentry defaults:
  - `attach_stacktrace`
  - `include_local_variables`
  - `debug`
- Move Sentry profile sample rate out of experimental configuration

## 2024-01-30 - 0.0.6

Fixes:

- Formatting fixup in `__version__.py`
- Ensure STDOUT is flushed on route announce/withdraw
- Define `app_url` for Apprise
- Change line breaks for Apprise notification as they are broken in Slack
- Debug or trace level logging must be enabled to log the Python filename/line number/function name in file/syslog

Changes:

- ExaCheck internal configuration (eg. for the `live_reload` feature) has been migrated out of the base `Settings` class. Instead, ExaCheck configuration now resides in its own `settings.ExaCheck` class.

## 2024-01-29 - 0.0.5

Fixes:

- ExaBGP fails to start on Python 3.12. ExaCheck now requires Python 3.11.

Features

- Docker deployment now available - see the [ExaCheck Docker deployment page](https://exacheck.net/deployment/docker/) for instructions.

## 2024-01-29 - 0.0.4

Fixes:

- Replace static version definition in `__version__.py` with `importlib.metadata` lookup

Features:

- Add support for Python 3.11

Misc:

- Update Apprise and dnspython

## 2024-01-29 - 0.0.3

Fixes:

- Add CHANGELOG.md

## 2024-01-29 - 0.0.3a0

Fixes:

- Adds dependency on `loguru` and `click` correctly

## 2024-01-29 - 0.0.2

Initial public release
