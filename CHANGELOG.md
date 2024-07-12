# ExaCheck Changelog

## PENDING - 0.1.4

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
