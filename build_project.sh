#!/bin/bash

# Pass arguments to the script
branch=$1
url=$2
directory=$3
customPath=$4
postprocess=$5 # For later

# Function to configure git for private repo access
configure_git() {
    local token=$1
    local orgName=$2

    # Set temporary global configuration
    git config --global url."https://git:${token}@github.com/${orgName}".insteadOf "https://github.com/${orgName}"
    git config --global url."https://github.com/".insteadOf "git@github.com:"
}

# Function to revert git configuration changes
revert_git_config() {
    local orgName=$1

    # Revert temporary global configuration
    git config --global --remove-section url."https://git@github.com/${orgName}" > /dev/null 2>&1
    git config --global --remove-section url."https://github.com/" > /dev/null 2>&1
}

# Is this a private repo?
if [[ "$url" =~ https://git:([^@]+)@github.com ]]; then
    echo "RUN: Git Clone Private"
    token="${BASH_REMATCH[1]}"
    orgName=$(echo $url | grep -oP '(?<=github.com/)[^/]+')

    # Configure git temporarily
    configure_git "$token" "$orgName"

    # Perform the clone
    git clone --recurse-submodules -b ${branch} --single-branch ${url} ${directory}

    # Immediately revert the git configuration to avoid affecting other operations
    revert_git_config "$orgName"
else
    # Clone the repo without special configuration
    git clone --recurse-submodules -b ${branch} --single-branch ${url} ${directory}
fi

# Change directory
cd ${customPath}

# Extract the package manager from the preinstall script in package.json
PACKAGE_JSON="package.json"
PACKAGE_MANAGER=$(jq -r '.scripts.preinstall' $PACKAGE_JSON | grep -oE 'npm|pnpm|yarn')

if [ -z "$PACKAGE_MANAGER" ]; then
    echo "No package manager found in the preinstall script. Defaulting to yarn."
    PACKAGE_MANAGER="yarn"
fi

# 1. Package manager install
echo "Running ${PACKAGE_MANAGER} install --ignore-scripts"
${PACKAGE_MANAGER} install --ignore-scripts || { echo "${PACKAGE_MANAGER} install failed"; exit 1; }

# 2. Git submodule update with error handling
echo "Updating git submodules"
if git submodule update --init --recursive; then
    echo "Git submodule update successful"
else
    echo "Git submodule update failed, but continuing with the script."
fi

# 3. Forge install
echo "Running forge install"
forge install

# Run build command
echo "Building the project"
forge build --ast

# Run postprocess if specified
if [ -n "$postprocess" ]; then
    echo "Running postprocess command: $postprocess"
    eval $postprocess
fi