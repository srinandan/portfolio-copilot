#!/bin/bash
set -e

# Delegate to infra/setup_model_armor.sh
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
exec bash "$DIR/../infra/setup_model_armor.sh" "$@"
