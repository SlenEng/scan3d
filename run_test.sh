#!/bin/bash
echo "======================================"
echo "  SCAN3D — Test Pipeline Automatique"
echo "======================================"
cd "$(dirname "$0")"

if [ -f /workspaces/scan3d/venv/bin/activate ]; then
    source /workspaces/scan3d/venv/bin/activate
elif [ -f ~/venv/bin/activate ]; then
    source ~/venv/bin/activate
fi

cd backend
python test_pipeline.py
