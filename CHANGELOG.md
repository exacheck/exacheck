## Unreleased - 0.0.6

Fixes:

- Formatting fixup in `__version__.py`
- Ensure STDOUT is flushed on route announce/withdraw
- Define `app_url` for Apprise
- Change line breaks for Apprise notification as they are broken in Slack

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
