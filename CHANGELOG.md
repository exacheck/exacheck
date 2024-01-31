## UNRELEASED - 0.0.7

Fixes:

- Correct the logging event types for announce/withdraw of routes for log filtering to work correctly

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
