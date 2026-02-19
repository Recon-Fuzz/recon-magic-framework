# =============================================================================
# MERGED Dockerfile: runner + recon-magic-framework
# Base: runner's Ubuntu 24.04 (more comprehensive than framework's python:3.12-slim)
#
# Runs as root. Claude Code's --dangerously-skip-permissions root restriction
# is bypassed via IS_SANDBOX=1 (official escape hatch).
# =============================================================================
# OPTIMIZATION: Consider multi-stage build to reduce final image size
# OPTIMIZATION: Combine apt-get layers to reduce image layers

FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /home/ubuntu

# =============================================================================
# [RUNNER] OS libraries
# =============================================================================
RUN echo "Install OS libraries"

RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
    curl gcc make python3-pip python3-venv unzip jq wget tar software-properties-common \
    git build-essential autoconf libffi-dev cmake ninja-build zlib1g-dev \
    libboost-all-dev flex bison && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# =============================================================================
# [FRAMEWORK] Additional OS packages not in runner's list
# =============================================================================
RUN apt-get update && apt-get install -y --no-install-recommends \
    ripgrep sudo && \
    apt-get clean && rm -rf /var/lib/apt/lists/*
# OPTIMIZATION: Merge this into the apt-get block above

# =============================================================================
# [RUNNER] Ensure git is available
# =============================================================================
RUN git --version

# =============================================================================
# [RUNNER] Install Node.js via NVM (v20.18.0)
# Framework used nodesource v20 — runner's NVM approach is more explicit, keeping this one
# =============================================================================
ENV NODE_VERSION=20.18.0
RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.3/install.sh | bash && \
  export NVM_DIR=/root/.nvm && \
  . "$NVM_DIR/nvm.sh" && nvm install ${NODE_VERSION} && nvm alias default v${NODE_VERSION} && nvm use default
ENV NVM_DIR=/root/.nvm
ENV PATH="$NVM_DIR/versions/node/v${NODE_VERSION}/bin/:${PATH}"
RUN corepack enable

# =============================================================================
# [RUNNER] Python venv
# Framework used python:3.12-slim as base, so python was built-in.
# On Ubuntu 24.04 we need to set up python ourselves.
# =============================================================================
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# =============================================================================
# [RUNNER] Install solc-select + solc 0.8.24
# =============================================================================
RUN pip3 install solc-select
RUN solc-select install 0.8.24 && solc-select use 0.8.24

# =============================================================================
# [RUNNER] Install slither and hexbytes
# =============================================================================
RUN pip3 install hexbytes slither-analyzer && slither --version

# =============================================================================
# [RUNNER] Install Echidna (custom fork: Recon-Fuzz/echidna-exp)
# Framework used Homebrew to install echidna — runner's binary is a custom fork,
# keeping this one. Homebrew install is dropped entirely.
# =============================================================================
RUN wget https://github.com/Recon-Fuzz/echidna-exp/releases/download/latest/echidna-HEAD-2404131-x86_64-linux.tar.gz && \
  tar -xvkf echidna-HEAD-2404131-x86_64-linux.tar.gz && \
  mv echidna /usr/bin/ && rm echidna-HEAD-2404131-x86_64-linux.tar.gz && \
  echidna --version

# =============================================================================
# [RUNNER] Install Foundry
# Framework also installed foundry with a different approach (copied binaries to /opt/foundry/bin).
# Runner's approach is simpler — just foundryup + PATH.
# =============================================================================
RUN curl -L https://foundry.paradigm.xyz | bash && \
  export PATH="$PATH:/root/.foundry/bin" && \
  foundryup
ENV PATH="$PATH:/root/.foundry/bin"

RUN apt-get update && apt-get install -y glibc-source

# =============================================================================
# [RUNNER] Install Go 1.22.5
# Framework used Go 1.21.5 — runner's is newer, keeping this one.
# =============================================================================
RUN wget https://go.dev/dl/go1.22.5.linux-amd64.tar.gz && \
    tar -C /usr/local -xzf go1.22.5.linux-amd64.tar.gz && \
    rm go1.22.5.linux-amd64.tar.gz
ENV PATH="$PATH:/usr/local/go/bin"
RUN go version

RUN export PATH="$PATH:/usr/local/go/bin"
ENV PATH="$PATH:/usr/local/go/bin"
RUN go version

# =============================================================================
# [RUNNER] Install Medusa v1.4.1 (multi-arch)
# =============================================================================
ARG TARGETARCH
ARG TARGETOS=linux
ENV GOOS=${TARGETOS}
ENV GOARCH=${TARGETARCH}
ENV CGO_ENABLED=1

RUN git clone https://github.com/crytic/medusa && \
    cd medusa && git config pull.ff false && \
    git checkout 3857153837ab90ed73adc484414b4b43703a54fb && \
    go build -trimpath -o medusa && \
    mv medusa /usr/local/bin/ && chmod +x /usr/local/bin/medusa && \
    cd .. && rm -rf medusa

RUN medusa --version

# =============================================================================
# [RUNNER] Install clang (for Halmos dependencies)
# =============================================================================
RUN apt-get update && apt-get install -y clang

# =============================================================================
# [RUNNER] Install Halmos (via uv tool)
# This also installs uv, which the framework needs too (see below).
# =============================================================================
RUN echo "Install halmos"
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    echo 'export PATH="$PATH:/root/.local/bin"' >> /root/.bashrc && \
    echo 'export PATH="$PATH:/root/.local/bin"' >> /etc/profile && \
    export PATH="$PATH:/root/.local/bin" && \
    uv tool install --python 3.12 halmos && \
    ln -sf /root/.local/bin/halmos /usr/local/bin/halmos

RUN echo "Halmos installed, version:"
RUN halmos --version

# =============================================================================
# [RUNNER] Install AWS CLI
# =============================================================================
RUN curl "https://awscli.amazonaws.com/awscli-exe-linux-$(echo ${TARGETARCH} | sed 's/amd64/x86_64/;s/arm64/aarch64/').zip" -o "awscliv2.zip" && \
    unzip awscliv2.zip && ./aws/install && \
    rm -rf awscliv2.zip aws && \
    aws --version

RUN apt-get install -y zip netcat-openbsd glibc-source

# =============================================================================
# [RUNNER] Install Yices 2.6.4 (SMT solver)
# =============================================================================
WORKDIR /yices
ARG YICES_VERSION=2.6.4
RUN wget https://github.com/SRI-CSL/yices2/releases/download/Yices-${YICES_VERSION}/yices-${YICES_VERSION}-x86_64-pc-linux-gnu.tar.gz -O yices.tar.gz && \
    tar -xzvf yices.tar.gz --strip-components=1 && \
    mv /yices/bin/* /usr/local/bin/ && \
    mv /yices/lib/* /usr/local/lib/ && \
    mv /yices/include/* /usr/local/include/ && \
    rm -rf /yices

# =============================================================================
# [RUNNER] Install Bitwuzla (SMT solver, built from source)
# =============================================================================
RUN pip3 install meson
RUN apt-get update && apt-get install -y \
    pkg-config \
    libgmp-dev \
    libmpfr-dev \
    cmake \
    ninja-build
WORKDIR /bitwuzla
RUN git clone https://github.com/bitwuzla/bitwuzla . && \
    ./configure.py && \
    cd build && \
    ninja install

# =============================================================================
# [FRAMEWORK] Install uv as pip package (for framework's pyproject.toml usage)
# Runner already installed uv via install.sh above for halmos — this makes it
# available as a pip-level tool too.
# =============================================================================
RUN pip3 install uv
# OPTIMIZATION: uv is already installed via astral.sh above (for halmos).
# Could just symlink or use that one instead of double-installing.

# =============================================================================
# [FRAMEWORK] Install Node.js packages globally (claude-code, opencode-ai)
# =============================================================================
RUN npm install -g @anthropic-ai/claude-code opencode-ai

# =============================================================================
# [RUNNER + FRAMEWORK] Configure git
# Merged from both: runner's HTTPS rewrite rules + framework's user identity.
# =============================================================================
RUN git config --global user.email "recon@worker.local" && \
    git config --global user.name "Recon Worker" && \
    git config --global url."https://github.com/".insteadOf "git@github.com:" && \
    git config --global url."https://github.com/".insteadOf "git://github.com/"

WORKDIR /

# =============================================================================
# Copy entire monorepo into /app (single COPY to avoid overwrite issues)
# =============================================================================
WORKDIR /app
COPY . /app/

# =============================================================================
# [RUNNER] Copy halmos helper script to PATH
# =============================================================================
RUN cp /app/runner/run_halmos.sh /usr/local/bin/run_halmos.sh && \
    chmod +x /usr/local/bin/run_halmos.sh

# =============================================================================
# [FRAMEWORK] Install Python deps
# =============================================================================
RUN pip3 install -e .

# =============================================================================
# [RUNNER] Install Node deps (must be LAST so node_modules/ is not overwritten)
# =============================================================================
WORKDIR /app/runner

RUN --mount=type=secret,id=npm_token \
  echo "//registry.npmjs.org/:_authToken=$(cat /run/secrets/npm_token)" > .npmrc && \
  yarn install --frozen-lockfile

# =============================================================================
# [BACKEND] Install pnpm (needed by build_project.sh for user project builds)
# =============================================================================
RUN npm install -g pnpm only-allow@1.2.1

# =============================================================================
# [BACKEND] Install deps and compile TypeScript
# =============================================================================
WORKDIR /app/backend
RUN --mount=type=secret,id=npm_token \
  echo "//registry.npmjs.org/:_authToken=$(cat /run/secrets/npm_token)" > .npmrc && \
  yarn install --frozen-lockfile && \
  npx tsc
WORKDIR /app

# =============================================================================
# [SHARED] Prisma symlinks — both runner/ and backend/ resolve prisma/ to root
# =============================================================================
RUN ln -sf /app/prisma /app/backend/prisma && \
    ln -sf /app/prisma /app/runner/prisma

# =============================================================================
# [BACKEND] Make build_project.sh available globally
# =============================================================================
RUN cp /app/backend/build_project.sh /usr/local/bin/build_project.sh && \
    chmod +x /usr/local/bin/build_project.sh

# =============================================================================
# Claude Code root workaround
# Claude Code blocks --dangerously-skip-permissions when running as root.
# IS_SANDBOX=1 is the official escape hatch (confirmed by Anthropic).
# =============================================================================
ENV IS_SANDBOX=1

# =============================================================================
# [FRAMEWORK] Environment variables
# =============================================================================
ENV ANTHROPIC_API_KEY=""
ENV OPENROUTER_API_KEY=""

# =============================================================================
# Entrypoint: dispatches based on MODE env var
# MODE=runner    → yarn start (runner)
# MODE=api       → prisma db push + node dist/index.js (backend API)
# MODE=framework → python3 cli.py (framework CLI)
# MODE=worker    → python3 worker.py (framework worker/server)
# Default: framework
# =============================================================================
WORKDIR /app
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
