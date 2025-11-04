# Build: docker build -t recon-magic-framework .
# Run interactively: docker run -it recon-magic-framework /bin/bash
FROM python:3.12-slim

# Install Node.js
RUN apt-get update && apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# Install UV
RUN pip install uv

# Set working directory
WORKDIR /app

# Copy project files
COPY . .

# Install dependencies and build project
RUN uv tool install --editable .

## TOOD: MOve to something else


