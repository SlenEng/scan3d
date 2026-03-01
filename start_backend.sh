#!/bin/bash
echo "======================================"
echo "  SCAN3D — Démarrage Backend API"
echo "======================================"
cd "$(dirname "$0")"

# Activer le venv
if [ -f /workspaces/scan3d/venv/bin/activate ]; then
    source /workspaces/scan3d/venv/bin/activate
elif [ -f ~/venv/bin/activate ]; then
    source ~/venv/bin/activate
fi

# Créer les dossiers si nécessaire
mkdir -p backend/uploads backend/outputs

echo "→ API démarrée sur le port 8000"
echo "→ Docs Swagger: /docs"
echo ""
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
