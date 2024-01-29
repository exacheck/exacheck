# Set Python release to build/use
ARG PYTHON_VERSION=3.12

# Create base stage
FROM python:${PYTHON_VERSION}-slim AS base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=x \
    PATH="/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONOPTIMIZE=2

# Create builder stage
FROM base AS builder

# Set environment variables for build
ENV PIP_DEFAULT_TIMEOUT=100 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=off

# Install poetry
RUN python3 -m pip --no-cache-dir install poetry

# Change to work dir
WORKDIR /app

# Create venv
RUN python -m venv /venv

# Copy poetry files
COPY ./pyproject.toml ./poetry.lock ./

# Install dependencies
RUN . /venv/bin/activate && poetry install --no-dev --no-root

# Copy ExaCheck project
COPY . .

# Build ExaCheck wheel
RUN . /venv/bin/activate && poetry build

# Create final stage
FROM base AS runtime

# Copy venv and wheel from build stage
COPY --from=builder /venv /venv
COPY --from=builder /app/dist /app

# Install ExaCheck and cleanup
RUN . /venv/bin/activate && pip install --no-cache-dir /app/*.whl \
    && rm -rf /app

# Install startup script
COPY ./start.sh /start.sh

# Expose BGP port
EXPOSE 179/tcp

# Set start script
CMD ["/bin/bash", "/start.sh"]