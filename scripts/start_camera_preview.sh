#!/bin/bash
# Run from the Pi desktop so DISPLAY and desktop authentication are inherited.
set -eu
project_dir="$(cd -- "$(dirname -- "$0")/.." && pwd)"
if [ -x "$project_dir/venv/bin/python" ]; then
    exec "$project_dir/venv/bin/python" "$project_dir/camera_preview.py" "$@"
fi
exec python3 "$project_dir/camera_preview.py" "$@"
