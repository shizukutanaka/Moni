# Multi-stage Dockerfile for Moni System Monitor
# Production-ready with security hardening

# Build stage
FROM python:3.11-slim as builder

# Security: Create non-root user
RUN groupadd --gid 1000 moni \
    && useradd --uid 1000 --gid moni --shell /bin/bash --create-home moni

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    pkg-config \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libxrender1 \
    libxrandr2 \
    libxss1 \
    libgtk-3-0 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY --chown=moni:moni src/ src/
COPY --chown=moni:moni tests/ tests/
COPY --chown=moni:moni README.md ./

# Install package in development mode
RUN pip install --no-cache-dir -e .

# Run tests in build stage
RUN python -m pytest tests/ -v

# Production stage
FROM python:3.11-slim as production

# Security: Create non-root user
RUN groupadd --gid 1000 moni \
    && useradd --uid 1000 --gid moni --shell /bin/bash --create-home moni

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libxrender1 \
    libxrandr2 \
    libxss1 \
    libgtk-3-0 \
    libfontconfig1 \
    dbus-x11 \
    procps \
    iproute2 \
    net-tools \
    iputils-ping \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy Python environment from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Set working directory
WORKDIR /home/moni/app

# Copy application files
COPY --from=builder --chown=moni:moni /app/src ./src
COPY --chown=moni:moni pyproject.toml requirements.txt ./

# Install package
USER moni
RUN pip install --user --no-cache-dir -e .

# Create necessary directories
RUN mkdir -p /home/moni/.config/moni/{logs,exports,backups} \
    && mkdir -p /home/moni/.local/share/moni

# Security: Set secure permissions
USER root
RUN chown -R moni:moni /home/moni \
    && chmod -R 750 /home/moni/.config/moni \
    && chmod -R 755 /home/moni/app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import src.moni.main; print('Health check passed')" || exit 1

# Security: Switch to non-root user
USER moni

# Environment variables
ENV PYTHONPATH="/home/moni/app/src:$PYTHONPATH"
ENV MONI_CONFIG_DIR="/home/moni/.config/moni"
ENV MONI_LOG_LEVEL="INFO"
ENV MONI_ENABLE_SECURITY_LOGGING="true"

# Expose default port (if web interface is added)
EXPOSE 8080

# Set entrypoint
ENTRYPOINT ["python", "-m", "src.moni.main"]

# Labels for metadata
LABEL maintainer="Moni Development Team"
LABEL version="2.0.0"
LABEL description="Advanced system monitoring with real-time metrics and security"
LABEL licenses="MIT"