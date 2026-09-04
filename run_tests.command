#!/bin/bash
# Run the test suite. Stdlib unittest only -- no pip install needed.
cd "$(dirname "$0")"
PY="$(command -v python3 || command -v python)"
exec "$PY" -m unittest discover -s tests -v "$@"
