#!/bin/bash

# make script workdir relative
cd $(dirname "$0")

# validate docker daemon is running
if (! docker ps 2>&1>/dev/null); then
    echo "Docker is not running. Please start docker on your computer"
    exit 1;
fi

# execute all create_layer scripts
find . -name create_layer.sh -exec bash {} \;
