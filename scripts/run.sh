#!/bin/bash

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export PYTHONPATH=$PYTHONPATH:$PROJECT_ROOT

echo "🚀 Running script with PYTHONPATH=$PROJECT_ROOT"
python3 "$@"
