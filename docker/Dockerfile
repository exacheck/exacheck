# Set Python release to use as base
ARG PYTHON_VERSION=3.11

# Create base layer
FROM python:${PYTHON_VERSION}-slim AS base

# Set environment variables for Python
ENV PYTHONDONTWRITEBYTECODE=x \
    PYTHONUNBUFFERED=1 \
    PYTHONOPTIMIZE=2

# Set environment variables for pip
ENV PIP_DEFAULT_TIMEOUT=100 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=off

# Set environment variables for venv
ENV PATH=/app/bin:$PATH \
    VIRTUAL_ENV=/app

# Create build layer to create venv and install requirements
FROM base AS build

# Set ExaBGP release to install
ARG EXABGP_VERSION=4.2

# Create the new venv
RUN python3 -m venv /app

# Install required packages for ExaCheck
RUN apt-get update \
    # Install git to clone ExaBGP
    && apt-get install -y --no-install-recommends \
        git \
    # Upgrade pip, wheel and setuptools
    && python3 -m pip --no-cache-dir install --upgrade \
        pip \
        setuptools \
        wheel \
    # Install dumb-init
    && python3 -m pip --no-cache-dir install \
        dumb-init \
    # Install ExaBGP from source - this is required for Python 3.12 compatibility
    # until the PyPi release of ExaBGP is updated
    && python3 -m pip --no-cache-dir install \
        "git+https://github.com/Exa-Networks/exabgp.git@${EXABGP_VERSION}"

# Copy over the project source files
COPY . /exacheck

# Install ExaCheck and requirements
RUN python3 -m pip --no-cache-dir install /exacheck

# Create final layer
FROM base AS exacheck

# Copy out the venv from the build layer
COPY --from=build /app /app

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

# Set entrypoint and run ExaBGP
ENTRYPOINT ["/app/bin/dumb-init", "--"]
CMD ["/app/bin/exabgp", "/etc/exabgp/exabgp.conf"]
