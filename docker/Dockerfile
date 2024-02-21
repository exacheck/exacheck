# Set Python release to use as base
ARG PYTHON_VERSION=3.11

# Use Python image
FROM python:${PYTHON_VERSION}-slim

# Set environment variables for Python
ENV PYTHONDONTWRITEBYTECODE=x \
    PYTHONUNBUFFERED=1 \
    PYTHONOPTIMIZE=2

# Set environment variables for pip
ENV PIP_DEFAULT_TIMEOUT=100 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=off

# Add ExaBGP user and setup permissions
RUN useradd -Ms /bin/bash exabgp \
    && mkfifo /run/exabgp.in /run/exabgp.out \
    && chown -R exabgp:exabgp /run/exabgp.in /run/exabgp.out \
    && chmod 600 /run/exabgp.in /run/exabgp.out

# Set ExaCheck tag/branch to install
ARG EXACHECK_VERSION=v0.0.11

# Set path to the git repository for ExaCheck
ARG EXACHECK_REPOSITORY=https://github.com/exacheck/exacheck.git

# Install requirements and ExaCheck
RUN apt-get update \
    # Install git to clone ExaCheck
    && apt-get install -y --no-install-recommends \
        git \
    # Upgrade pip, wheel and setuptools
    && python3 -m pip --no-cache-dir install --upgrade \
        pip \
        setuptools \
        wheel \
    # Install dumb-init/ExaCheck
    && python3 -m pip --no-cache-dir install \
        dumb-init \
        "git+${EXACHECK_REPOSITORY}@${EXACHECK_VERSION}" \
    # Remove git and clean up
    && apt-get remove -y git \
    && apt-get --purge autoremove -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

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
