FROM ubuntu:24.04

# ARG NPM_TOKEN

RUN set -eux

ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /home/ubuntu

RUN echo "Install OS libraries"

## Production:
RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
    curl gcc make python3-pip python3-venv unzip jq wget tar software-properties-common \
    git build-essential autoconf libffi-dev cmake ninja-build zlib1g-dev \
    libboost-all-dev flex bison && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Ensure git is available in PATH
RUN git --version


# Install Node.js using NVM
ENV NODE_VERSION=20.18.0
RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.3/install.sh | bash && \
  export NVM_DIR=/root/.nvm && \
  . "$NVM_DIR/nvm.sh" && nvm install ${NODE_VERSION} && nvm alias default v${NODE_VERSION} && nvm use default
ENV NVM_DIR=/root/.nvm
ENV PATH="$NVM_DIR/versions/node/v${NODE_VERSION}/bin/:${PATH}"
RUN corepack enable

## Use venv for python
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install solc-select
RUN pip3 install solc-select

# Install solc 0.8.24
RUN solc-select install 0.8.24 && solc-select use 0.8.24

# Install slither and hexbytes
RUN pip3 install hexbytes slither-analyzer && slither --version

# Install echidna
# Official release
RUN wget https://github.com/Recon-Fuzz/echidna-exp/releases/download/latest/echidna-HEAD-2404131-x86_64-linux.tar.gz && \
  tar -xvkf echidna-HEAD-2404131-x86_64-linux.tar.gz && \
  mv echidna /usr/bin/ && rm echidna-HEAD-2404131-x86_64-linux.tar.gz && \
  echidna --version

# Install foundry
RUN curl -L https://foundry.paradigm.xyz | bash && \
  export PATH="$PATH:/root/.foundry/bin" && \
  foundryup
ENV PATH="$PATH:/root/.foundry/bin"

RUN apt-get update && apt-get install -y glibc-source

# Install Go
## Production:
RUN wget https://go.dev/dl/go1.22.5.linux-amd64.tar.gz && \
    tar -C /usr/local -xzf go1.22.5.linux-amd64.tar.gz && \
    rm go1.22.5.linux-amd64.tar.gz
ENV PATH="$PATH:/usr/local/go/bin"
RUN go version


RUN export PATH="$PATH:/usr/local/go/bin"
ENV PATH="$PATH:/usr/local/go/bin"
RUN go version

# Install medusa
## Production:
# Latest: 3857153837ab90ed73adc484414b4b43703a54fb ( v1.4.1 )
RUN git clone https://github.com/crytic/medusa && \
    cd medusa && git config pull.ff false && git checkout 3857153837ab90ed73adc484414b4b43703a54fb && \
    GOOS=linux GOARCH=amd64 go build && \
    mv medusa /usr/local/bin/ && chmod +x /usr/local/bin/medusa && \
    rm -rf /medusa
RUN medusa --version

# Install clang for Halmos dependencies
RUN apt-get update && apt-get install -y clang

# Install halmos
RUN echo "Install halmos"
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    echo 'export PATH="$PATH:/root/.local/bin"' >> /root/.bashrc && \
    echo 'export PATH="$PATH:/root/.local/bin"' >> /etc/profile && \
    export PATH="$PATH:/root/.local/bin" && \
    uv tool install --python 3.12 halmos && \
    ln -sf /root/.local/bin/halmos /usr/local/bin/halmos

RUN echo "Halmos installed, version:"
RUN halmos --version

# Install AWS CLI
## Production:
RUN curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" && \
  unzip awscliv2.zip && ./aws/install && \
  rm -rf awscliv2.zip aws && \
  aws --version

RUN apt-get install -y zip netcat-openbsd glibc-source

## SOLVERS

# Install Yices from the release binaries | NOTE: Seems to be mandatory
WORKDIR /yices
ARG YICES_VERSION=2.6.4
RUN wget https://github.com/SRI-CSL/yices2/releases/download/Yices-${YICES_VERSION}/yices-${YICES_VERSION}-x86_64-pc-linux-gnu.tar.gz -O yices.tar.gz && \
    tar -xzvf yices.tar.gz --strip-components=1 && \
    mv /yices/bin/* /usr/local/bin/ && \
    mv /yices/lib/* /usr/local/lib/ && \
    mv /yices/include/* /usr/local/include/ && \
    rm -rf /yices

# Install Bitwuzla
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


## END SOLVERS
# Configure git for reconuser
RUN git config --global user.email "recon_runner@worker.local" && \
    git config --global user.name "Recon Runner" && \
    git config --global url."https://github.com/".insteadOf "git@github.com:" && \
    git config --global url."https://github.com/".insteadOf "git://github.com/"

    
WORKDIR /



RUN cd /

# Check that
# Grant the bash scripts the necessary permissions
COPY run_halmos.sh /usr/local/bin/run_halmos.sh
RUN chmod +x /usr/local/bin/run_halmos.sh

RUN cd /

# Copy the node app
COPY . .

USER root

RUN --mount=type=secret,id=npm_token \
  echo "//registry.npmjs.org/:_authToken=$(cat /run/secrets/npm_token)" > .npmrc && \
  yarn install --frozen-lockfile
ENTRYPOINT yarn start "$@"
