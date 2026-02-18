## This Dockerfile is here to help you make Echidna work if you have issues with the installation of it or slither

## Built with
## docker build -t recon/backend .
## docker run -p 6969:6969 -it --rm recon/runner

FROM ubuntu:20.04

RUN set -eux

ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /home/ubuntu

ARG NPM_TOKEN
ENV NPM_TOKEN=${NPM_TOKEN}

RUN echo "Install OS libraries"
RUN apt-get update
RUN apt-get upgrade -y
## NOTE: Some of these are prob useless
RUN apt-get install -y curl gcc make unzip jq wget tar software-properties-common

RUN echo "Install Node 20"
ENV NODE_VERSION=20.11.0
RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.3/install.sh | bash
ENV NVM_DIR=/root/.nvm
RUN . "$NVM_DIR/nvm.sh" && nvm install ${NODE_VERSION}
RUN . "$NVM_DIR/nvm.sh" && nvm use v${NODE_VERSION}
RUN . "$NVM_DIR/nvm.sh" && nvm alias default v${NODE_VERSION}
ENV PATH="$NVM_DIR/versions/node/v${NODE_VERSION}/bin/:${PATH}"
RUN node --version
RUN npm --version
RUN npm install --global yarn
RUN yarn --version

RUN echo "Install Git"
RUN add-apt-repository -y ppa:git-core/ppa
RUN apt-get update
RUN apt-get install -y git

RUN echo "Install foundry"
RUN curl -L https://foundry.paradigm.xyz | bash
RUN export PATH="$PATH:/root/.foundry/bin"
ENV PATH="$PATH:/root/.foundry/bin"
RUN PATH="$PATH:/root/.foundry/bin" foundryup

## Some projects require pnpm (like optimism)
RUN npm install -g pnpm
RUN npm install -g only-allow@1.2.1

## Copy all files
COPY . .

## Grant necessary permissions
RUN chmod +x build_project.sh

RUN echo "//registry.npmjs.org/:_authToken=${NPM_TOKEN}" > .npmrc

## Install deps
RUN yarn

## Build
RUN yarn build

## Start
CMD ["yarn", "start"]
