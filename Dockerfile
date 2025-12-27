# docker build -t recon-magic-framework .
# docker run -it recon-magic-framework /bin/bash

# docker run -it -v .:/source:ro recon-magic-framework bash -c "cp -r /source /workspace && /bin/bash"
FROM python:3.12-slim

# Create non-root user early
RUN useradd -m -s /bin/bash reconuser

# Install Node.js and Go
RUN apt-get update && apt-get install -y curl git wget ripgrep sudo jq && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    wget https://go.dev/dl/go1.21.5.linux-amd64.tar.gz && \
    tar -C /usr/local -xzf go1.21.5.linux-amd64.tar.gz && \
    rm go1.21.5.linux-amd64.tar.gz && \
    rm -rf /var/lib/apt/lists/*

ENV PATH="/usr/local/go/bin:${PATH}"
ENV GOPATH="/opt/go"
ENV PATH="${GOPATH}/bin:${PATH}"

# Install Homebrew
RUN useradd -m -s /bin/bash linuxbrew && \
    echo 'linuxbrew ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers
USER linuxbrew
RUN /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
ENV PATH="/home/linuxbrew/.linuxbrew/bin:${PATH}"
RUN brew install echidna
USER root

# Make linuxbrew home directory traversable for other users (needed for echidna access)
RUN chmod 755 /home/linuxbrew

# Install UV
RUN pip install uv

# Install Node.js packages globally
RUN npm install -g @anthropic-ai/claude-code opencode-ai

# Install Medusa fuzzer (to shared location)
RUN mkdir -p /opt/go && \
    GOPATH=/opt/go go install github.com/crytic/medusa@latest && \
    chmod -R 755 /opt/go

# Install Foundry (to shared location)
ENV FOUNDRY_DIR="/opt/foundry"
RUN curl -L https://foundry.paradigm.xyz | bash && \
    . /root/.bashrc && foundryup && \
    mkdir -p /opt/foundry/bin && \
    find /root/.foundry -name "forge" -o -name "cast" -o -name "anvil" -o -name "chisel" | xargs -I {} cp {} /opt/foundry/bin/ && \
    chmod -R 755 /opt/foundry
ENV PATH="/opt/foundry/bin:${PATH}"

# Set working directory
WORKDIR /app

# Copy project files
COPY . .

# Install dependencies and build project
RUN pip install --break-system-packages -e .

# Install Slither for cyclomatic complexity analysis
RUN pip install --break-system-packages slither-analyzer

# Setup reconuser permissions
RUN mkdir -p /tmp && \
    chown -R reconuser:reconuser /tmp /app && \
    echo 'reconuser ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers

# Ensure echidna binaries are executable by reconuser (defense-in-depth)
RUN chmod -R 755 /home/linuxbrew/.linuxbrew/bin

# Switch to non-root user
USER reconuser

# Configure git for reconuser
RUN git config --global user.email "recon@worker.local" && \
    git config --global user.name "Recon Worker"

# Set working directory to /tmp for user operations
WORKDIR /tmp

# Environment variables (override at runtime with -e flag)
ENV ANTHROPIC_API_KEY=""
ENV OPENROUTER_API_KEY=""