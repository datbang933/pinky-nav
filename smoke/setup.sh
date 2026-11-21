#!/usr/bin/env bash
# Creates ../.venv (system site packages so ROS 2 python modules stay importable) and installs the smoke-detector deps.
# CPU-only torch (YOLOv8n runs ~35 ms/frame on a laptop CPU). numpy<2 is required: ROS 2 Jazzy's apt packages are built against numpy 1.x.
set -e
cd "$(dirname "$0")/.."
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -U pip
.venv/bin/pip install "numpy<2"
.venv/bin/pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
.venv/bin/pip install -r smoke/requirements.txt "numpy<2"
echo "done. Put the model at smoke/models/rabahdev/best.pt (see smoke/README.md), then:"
echo "  .venv/bin/python tools/smoke_response.py --dry-run --source 0"
