#!/bin/bash
set -e

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║     SCAN3D — Setup GitHub Codespaces    ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# System dependencies for OpenCV + Open3D
echo ">>> [1/3] Dépendances système..."
sudo apt-get update -qq 2>/dev/null
sudo apt-get install -y -qq \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    libgomp1 \
    2>/dev/null
echo "    ✓ OK"

# Python virtualenv
echo ">>> [2/3] Environnement Python..."
cd /workspaces/scan3d
python -m venv venv
source venv/bin/activate
pip install --upgrade pip --quiet
echo "    ✓ OK"

# Python packages
echo ">>> [3/3] Packages Python (Open3D ~500MB — 5-10 min)..."
source /workspaces/scan3d/venv/bin/activate
pip install fastapi==0.111.0 "uvicorn[standard]==0.29.0" python-multipart==0.0.9 --quiet
echo "    ✓ FastAPI OK"
pip install numpy==1.26.4 scipy==1.13.0 --quiet
echo "    ✓ NumPy OK"
pip install opencv-python-headless==4.9.0.80 --quiet
echo "    ✓ OpenCV OK"
pip install Pillow==10.3.0 requests --quiet
echo "    ✓ Pillow OK"
pip install open3d==0.18.0 --quiet
echo "    ✓ Open3D OK"

# Create required folders
mkdir -p /workspaces/scan3d/backend/uploads
mkdir -p /workspaces/scan3d/backend/outputs

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║        ✅  SETUP COMPLET !              ║"
echo "╠══════════════════════════════════════════╣"
echo "║                                          ║"
echo "║  ÉTAPE 1 - Terminal 1 (Backend) :        ║"
echo "║  bash start_backend.sh                   ║"
echo "║                                          ║"
echo "║  ÉTAPE 2 - Terminal 2 (Frontend) :       ║"
echo "║  bash start_frontend.sh                  ║"
echo "║                                          ║"
echo "║  TEST AUTOMATIQUE :                      ║"
echo "║  bash run_test.sh                        ║"
echo "║                                          ║"
echo "╚══════════════════════════════════════════╝"
echo ""
