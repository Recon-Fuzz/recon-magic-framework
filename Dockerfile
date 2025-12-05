# docker build -t recon-magic-framework .
# docker run -it recon-magic-framework /bin/bash

# docker run -it -v .:/source:ro recon-magic-framework bash -c "cp -r /source /workspace && /bin/bash"
FROM python:3.12-slim

# Install Node.js and Go
RUN apt-get update && apt-get install -y curl git wget ripgrep && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    wget https://go.dev/dl/go1.21.5.linux-amd64.tar.gz && \
    tar -C /usr/local -xzf go1.21.5.linux-amd64.tar.gz && \
    rm go1.21.5.linux-amd64.tar.gz && \
    rm -rf /var/lib/apt/lists/*

ENV PATH="/usr/local/go/bin:${PATH}"
ENV GOPATH="/root/go"
ENV PATH="${GOPATH}/bin:${PATH}"

# Install Homebrew
RUN useradd -m -s /bin/bash linuxbrew && \
    echo 'linuxbrew ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers
USER linuxbrew
RUN /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
ENV PATH="/home/linuxbrew/.linuxbrew/bin:${PATH}"
RUN brew install echidna
USER root

# Install UV
RUN pip install uv

# Install Node.js packages globally
RUN npm install -g @anthropic-ai/claude-code opencode-ai

# Install Medusa fuzzer
RUN go install github.com/crytic/medusa@latest

# Install Foundry
RUN curl -L https://foundry.paradigm.xyz | bash
ENV PATH="/root/.foundry/bin:${PATH}"
RUN foundryup

# Set working directory
WORKDIR /app

# Copy project files
COPY . .

# Install dependencies and build project
RUN pip install --break-system-packages -e .

# Create non-root user for running commands
RUN useradd -m -s /bin/bash reconuser && \
    mkdir -p /tmp && \
    chown -R reconuser:reconuser /tmp /app

# Switch to non-root user
USER reconuser

# Set working directory to /tmp for user operations
WORKDIR /tmp

# Environment variables (override at runtime with -e flag)
ENV ANTHROPIC_API_KEY=""
ENV OPENROUTER_API_KEY=""

## Run a command to clone a project
## Clone some prompts
## Run some tests.