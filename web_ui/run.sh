#!/bin/bash

# TermiVoxed Web UI - Quick Run Script (Unix/Linux/macOS)
# Author: Santhosh T
#
# This is a simple alias to start.sh for convenience

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
exec "$SCRIPT_DIR/start.sh" "$@"
