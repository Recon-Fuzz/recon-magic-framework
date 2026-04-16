# Dockerfile Security: Choosing the Right Base Image

## The Problem with Ubuntu

Our current Dockerfiles use `ubuntu:24.04`, which ships with **50+ CVEs** out of the box. Every unnecessary package is an attack vector.

---

## Base Image Comparison (2025 Data)

| Image | CVEs | Size | glibc | Package Manager | Notes |
|-------|------|------|-------|-----------------|-------|
| **Chainguard** | 0 | Smallest | ✅ | apk (build only) | Rebuilt nightly, 7-day CVE SLA |
| **Google Distroless** | 0 | Small | ✅ | None | No shell, Bazel-based |
| **Wolfi** | 0 | Small | ✅ | apk | Chainguard's open-source base |
| Debian Slim | 2 | Medium | ✅ | apt | Decent compromise |
| Alpine | 11+ | Small | ❌ musl | apk | busybox vulnerabilities |
| Ubuntu | 50+ | Large | ✅ | apt | Lots of unnecessary packages |

**Source**: [Container Base Image Vulnerability Comparison](https://images.latio.com/)

---

## Why Chainguard/Wolfi?

### 1. Zero CVEs
Images are rebuilt nightly with all security patches. Chainguard offers:
- **7-day SLA** for critical CVEs
- **14-day SLA** for high/medium/low

### 2. Distroless Philosophy
Final images contain only:
- Application binary
- Runtime dependencies
- No shell, no package manager, no wget/curl

### 3. glibc (Not musl)
Unlike Alpine, Wolfi uses **glibc**, which means:
- Pre-built binaries work (echidna, medusa)
- No weird compatibility issues
- Better performance for some workloads

### 4. Smaller Than Alpine
```
hello-world:alpine     → 25.5 MB
hello-world:chainguard → 19.9 MB
hello-world:scratch    → 12.6 MB
```

### 5. Built-in SBOM
Every image includes a Software Bill of Materials for supply chain security.

---

## Our Tool Requirements

We need all of these in one image:

| Tool | Source | Works on Wolfi? |
|------|--------|-----------------|
| Node 20 | apk | ✅ `apk add nodejs npm` |
| Python 3 | apk | ✅ `apk add python-3 py3-pip` |
| Go 1.22 | apk | ✅ `apk add go` |
| Git | apk | ✅ `apk add git` |
| Foundry | curl install | ✅ (glibc binary) |
| Echidna | binary release | ✅ (glibc binary) |
| Medusa | go build | ✅ |
| Halmos | pip install | ✅ |
| Slither | pip install | ✅ |
| claude-code | npm install | ✅ |
| opencode-ai | npm install | ✅ |
| AWS CLI | pip/binary | ✅ |
| Bitwuzla | build from source | ⚠️ needs cmake/ninja |
| Yices | binary release | ✅ (glibc binary) |

---

## Recommended Dockerfile: Multi-Stage Wolfi

```dockerfile
# =============================================================================
# Stage 1: Builder - Install all tools
# =============================================================================
FROM cgr.dev/chainguard/wolfi-base AS builder

# Install build dependencies
RUN apk update && apk add --no-cache \
    build-base \
    cmake \
    ninja \
    git \
    curl \
    wget \
    go \
    nodejs \
    npm \
    python-3 \
    py3-pip

# === GO TOOLS ===
ENV GOPATH=/go
ENV PATH="$GOPATH/bin:$PATH"

# Install Medusa
RUN git clone https://github.com/crytic/medusa /tmp/medusa && \
    cd /tmp/medusa && \
    go build -o /usr/local/bin/medusa && \
    rm -rf /tmp/medusa

# === FOUNDRY ===
RUN curl -L https://foundry.paradigm.xyz | bash
ENV PATH="/root/.foundry/bin:$PATH"
RUN foundryup

# === ECHIDNA (pre-built binary) ===
RUN wget https://github.com/crytic/echidna/releases/download/v2.3.0-RC2/echidna-2.3.0-RC2-x86_64-linux.tar.gz && \
    tar -xf echidna-*.tar.gz && \
    mv echidna /usr/local/bin/ && \
    rm echidna-*.tar.gz

# === YICES (pre-built binary) ===
RUN wget https://github.com/SRI-CSL/yices2/releases/download/Yices-2.6.4/yices-2.6.4-x86_64-pc-linux-gnu.tar.gz && \
    tar -xzf yices-*.tar.gz && \
    mv yices-*/bin/* /usr/local/bin/ && \
    mv yices-*/lib/* /usr/local/lib/ && \
    rm -rf yices-*

# === PYTHON TOOLS ===
RUN pip3 install --no-cache-dir \
    solc-select \
    slither-analyzer \
    halmos

# === NODE TOOLS ===
RUN npm install -g \
    @anthropic-ai/claude-code \
    opencode-ai

# === AWS CLI ===
RUN pip3 install --no-cache-dir awscli

# =============================================================================
# Stage 2: Runtime - Minimal image with only what we need
# =============================================================================
FROM cgr.dev/chainguard/wolfi-base AS runtime

# Install only runtime dependencies (no build tools)
RUN apk update && apk add --no-cache \
    git \
    nodejs \
    npm \
    python-3 \
    py3-pip \
    libstdc++ \
    gcompat

# Copy binaries from builder
COPY --from=builder /usr/local/bin/medusa /usr/local/bin/
COPY --from=builder /usr/local/bin/echidna /usr/local/bin/
COPY --from=builder /usr/local/bin/yices* /usr/local/bin/
COPY --from=builder /usr/local/lib/libyices* /usr/local/lib/
COPY --from=builder /root/.foundry/bin/* /usr/local/bin/

# Copy Python packages
COPY --from=builder /usr/lib/python3*/site-packages /usr/lib/python3/site-packages

# Copy Node global packages
COPY --from=builder /usr/lib/node_modules /usr/lib/node_modules
RUN ln -s /usr/lib/node_modules/@anthropic-ai/claude-code/cli.js /usr/local/bin/claude
RUN ln -s /usr/lib/node_modules/opencode-ai/bin/opencode /usr/local/bin/opencode

# Set up non-root user
RUN adduser -D -u 1000 reconuser
USER reconuser

WORKDIR /app
```

---

## Alternative: Hardened Ubuntu (If Wolfi Doesn't Work)

If tool compatibility issues arise, harden Ubuntu instead:

```dockerfile
FROM ubuntu:24.04

# Install only what's needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# ... install tools ...

# Remove unnecessary packages and clean up
RUN apt-get purge -y \
    gcc \
    make \
    && apt-get autoremove -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /tmp/* \
    && rm -rf /root/.cache

# Remove shells if not needed (WARNING: breaks AI tools)
# RUN rm /bin/bash /bin/sh

# Run as non-root
RUN useradd -m -u 1000 reconuser
USER reconuser
```

---

## Security Checklist

### Must Do
- [ ] Use non-root user (`USER reconuser`)
- [ ] Multi-stage build (don't ship build tools)
- [ ] Pin versions (not `:latest`)
- [ ] Remove package manager cache
- [ ] No secrets in image (use runtime env vars)

### Should Do
- [ ] Use Chainguard/Wolfi base
- [ ] Scan image with Trivy/Grype
- [ ] Sign images with cosign
- [ ] Generate SBOM

### Nice to Have
- [ ] Read-only root filesystem
- [ ] No new privileges (`--security-opt=no-new-privileges`)
- [ ] Seccomp profiles
- [ ] AppArmor profiles

---

## Image Scanning Commands

```bash
# Scan with Trivy
trivy image recon-runner:latest

# Scan with Grype
grype recon-runner:latest

# Generate SBOM
syft recon-runner:latest -o spdx-json > sbom.json
```

---

## Migration Plan

### Phase 1: Test Wolfi Compatibility
```bash
# Build test image
docker build -f Dockerfile.wolfi -t recon-test .

# Test each tool
docker run recon-test forge --version
docker run recon-test echidna --version
docker run recon-test medusa --version
docker run recon-test claude --version
```

### Phase 2: Benchmark
```bash
# Compare image sizes
docker images | grep recon

# Compare CVEs
trivy image recon-ubuntu:latest
trivy image recon-wolfi:latest
```

### Phase 3: Gradual Rollout
1. Deploy Wolfi image to staging
2. Run full test suite
3. Monitor for issues
4. Roll out to production

---

## References

- [Chainguard Images Overview](https://edu.chainguard.dev/chainguard/chainguard-images/overview/)
- [Wolfi with Dockerfiles](https://edu.chainguard.dev/open-source/wolfi/wolfi-with-dockerfiles/)
- [Container Base Image Vulnerability Comparison](https://images.latio.com/)
- [Alpine vs Distroless vs Scratch](https://medium.com/google-cloud/alpine-distroless-or-scratch-caac35250e0b)
- [Chainguard Zero CVE Benchmarks](https://www.chainguard.dev/unchained/zero-cves-and-just-as-fast-chainguards-python-go-images)
- [Making Container Images Better](https://iximiuz.com/en/posts/containers-making-images-better/)
