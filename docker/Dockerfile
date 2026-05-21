# syntax=docker/dockerfile:1

# Set Python release to use as base
ARG PYTHON_VERSION=3.13

# ExaCheck version (used as an OCI label). Override at build time with
# --build-arg EXACHECK_VERSION=$(poetry version -s)
ARG EXACHECK_VERSION=dev

# Create base layer
FROM python:${PYTHON_VERSION}-slim AS base

# Python runtime settings.
# - PYTHONDONTWRITEBYTECODE=1: no .pyc generation (smaller layers).
# - PYTHONUNBUFFERED=1: unbuffered stdout/stderr so Docker captures logs live.
# - PYTHONOPTIMIZE=1: strips docstrings only. Do NOT raise to 2 — that strips
#   `assert` statements, several of which are real preconditions in the
#   codebase (e.g. worker._degrade).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONOPTIMIZE=1

# pip settings. PIP_NO_CACHE_DIR is intentionally unset so pip uses its
# cache directory — that cache is mounted via BuildKit's
# --mount=type=cache below, so wheels survive layer invalidation across
# builds. The cache is not persisted into the final image because it
# lives in the discarded build stage's filesystem.
ENV PIP_DEFAULT_TIMEOUT=100 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# venv configuration
ENV PATH=/app/bin:$PATH \
    VIRTUAL_ENV=/app

# Create build layer to create venv and install requirements
FROM base AS build

# Create the new venv
RUN python3 -m venv /app

# Upgrade pip + install build helpers and dumb-init. The BuildKit cache
# mount preserves the pip wheel cache across builds.
RUN --mount=type=cache,target=/root/.cache/pip \
    python3 -m pip install --upgrade pip setuptools wheel \
    && python3 -m pip install dumb-init

# Copy over the project source files
COPY . /exacheck

# Install ExaCheck and requirements (reuses cached wheels from the mount
# when a source-only change invalidates this layer).
RUN --mount=type=cache,target=/root/.cache/pip \
    python3 -m pip install /exacheck

# Create final layer
FROM base AS exacheck

# Re-declare the build ARG inside this stage so it can populate the label.
ARG EXACHECK_VERSION

# OCI image labels — improves `docker inspect` legibility and supply-chain
# tooling (renovate, syft, etc.).
LABEL org.opencontainers.image.title="ExaCheck" \
      org.opencontainers.image.description="ExaCheck - ExaBGP Health Checker" \
      org.opencontainers.image.url="https://exacheck.net" \
      org.opencontainers.image.source="https://github.com/exacheck/exacheck" \
      org.opencontainers.image.documentation="https://exacheck.net/deployment/" \
      org.opencontainers.image.version="${EXACHECK_VERSION}"

# Copy out the venv from the build layer
COPY --from=build /app /app

# procps provides pgrep, used by the HEALTHCHECK below. Clean apt lists
# afterwards to keep the layer small.
RUN apt-get update \
    && apt-get install --no-install-recommends -y procps \
    && rm -rf /var/lib/apt/lists/*

# Add ExaBGP user and setup permissions
RUN useradd -Ms /bin/bash exabgp \
    && mkfifo /run/exabgp.in /run/exabgp.out \
    && chown -R exabgp:exabgp /run/exabgp.in /run/exabgp.out \
    && chmod 600 /run/exabgp.in /run/exabgp.out

# Switch to ExaBGP user
USER exabgp

# Set environment variables for ExaBGP
ENV exabgp.daemon.user=exabgp \
    exabgp.api.ack=false

# Expose BGP port
EXPOSE 179/tcp

# Container is considered healthy while the ExaBGP process is running.
# `start-period` gives ExaBGP a few seconds to come up before being
# marked unhealthy on initial container start.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD pgrep -f exabgp >/dev/null || exit 1

# Set entrypoint and run ExaBGP
ENTRYPOINT ["/app/bin/dumb-init", "--"]
CMD ["/app/bin/exabgp", "/etc/exabgp/exabgp.conf"]
