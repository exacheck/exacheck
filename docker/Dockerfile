# Set Python release to use as base
ARG PYTHON_VERSION=3.11

# Use Python image
FROM python:${PYTHON_VERSION}-slim

# Set ExaCheck release to install
ARG EXACHECK_VERSION=0.0.5

# Set environment variables for Python
ENV PYTHONDONTWRITEBYTECODE=x \
    PYTHONUNBUFFERED=1 \
    PYTHONOPTIMIZE=2

# Set environment variables for pip
ENV PIP_DEFAULT_TIMEOUT=100 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=off

# Install ExaCheck and requirements
RUN python3 -m pip --no-cache-dir install dumb-init exacheck==${EXACHECK_VERSION}

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
ENTRYPOINT ["/usr/local/bin/dumb-init", "--"]
CMD ["/usr/local/bin/exabgp", "/etc/exabgp/exabgp.conf"]
