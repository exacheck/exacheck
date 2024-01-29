#!/bin/bash

# Terminate if any command fails
set -e

# Enable conda
__conda_setup="$('/home/vscode/conda/bin/conda' 'shell.bash' 'hook' 2> /dev/null)"
if [ $? -eq 0 ]; then
    eval "$__conda_setup"
else
    if [ -f "/home/vscode/conda/etc/profile.d/conda.sh" ]; then
        . "/home/vscode/conda/etc/profile.d/conda.sh"
    else
        export PATH="/home/vscode/conda/bin:$PATH"
    fi
fi
unset __conda_setup

# Enter /code
cd /code

# Activate environment
conda activate exacheck

# Install requirements with poetry
poetry install --no-interaction --all-extras

echo "----------------------------------------------------------------------------"
echo "Python requirements installed"
echo "----------------------------------------------------------------------------"
