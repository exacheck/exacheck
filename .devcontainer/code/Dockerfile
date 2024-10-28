## Use Python base image
FROM registry.gitlab.com/development-images/ubuntu/python:latest

## Set default Python version to use
ENV USE_PYTHON_VERSION="3.13"

## Switch to root
USER root

## Copy startup scripts to container
COPY scripts /usr/local/scripts

## Add the zsh configuration file
COPY .zshrc /home/vscode/.zshrc

## Fix zshrc permissions
RUN chown vscode:vscode /home/vscode/.zshrc

## Install extra package requirements
RUN apt-get update && apt-get install -y --no-install-recommends \
        # Install LDAP development headers so python-ldap can be installed
        libldap2-dev libsasl2-dev \
        # Install watchman for Pyre
        watchman \
    ## Clean up
    && rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*

## Switch to the VS Code user
USER vscode

## Install Conda environment
RUN /home/vscode/conda/bin/conda create -q -y -n exacheck "python=${USE_PYTHON_VERSION}"

## Install rust; required to build 'pyre-check' with Python 3.13 currently
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y

## Set env var for the default path to the configuration file
ENV EXACHECK_CONFIG="/code/configuration.yaml"

## Set the work directory
WORKDIR /code
