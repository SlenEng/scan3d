#!/bin/bash
echo "======================================"
echo "  SCAN3D — Démarrage Frontend"
echo "======================================"
cd "$(dirname "$0")"

echo "→ Frontend démarré sur le port 3000"
echo "→ Ouvrez le port 3000 dans l'onglet PORTS de VS Code"
echo ""
cd frontend
python -m http.server 3000
