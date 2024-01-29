#!/bin/bash

set -euo pipefail

: "${EXABGP_CONFIGURATION:=/etc/exabgp/exabgp.conf}"
: "${EXABGP_ENV:=/etc/exabgp/exabgp.env}"
: "${EXACHECK_CONFIGURATION:=/etc/exabgp/exacheck.yaml}"

# Ensure the ExaBGP configuration file exists
while [ ! -f "$EXABGP_CONFIGURATION" ]; do
    echo "ExaBGP configuration file '${EXABGP_CONFIGURATION}' not found. Sleeping for 30 seconds."
    sleep 30
done

# Ensure the ExaCheck configuration file exists
while [ ! -f "$EXACHECK_CONFIGURATION" ]; do
    echo "ExaCheck configuration file '${EXACHECK_CONFIGURATION}' not found. Sleeping for 30 seconds."
    sleep 30
done

# Test that the ExaCheck configuration file is valid
while ! exacheck test -f "$EXACHECK_CONFIGURATION"; do
    echo "ExaCheck configuration file '${EXACHECK_CONFIGURATION}' is invalid. Sleeping for 30 seconds."
    sleep 30
done

# Create default ExaBGP env file if it does not already exist
if [ ! -f "$EXABGP_ENV" ]; then
    exabgp --fi > "$EXABGP_ENV"
fi

# Create named pipes for ExaBGP
mkfifo /run/exabgp.out
mkfifo /run/exabgp.in
chmod 777 /run/exabgp.out
chmod 777 /run/exabgp.in

# Execute ExaBGP
exabgp -e /etc/exabgp/exabgp.env /etc/exabgp/exabgp.conf
