# SCAN3D — Point Cloud Generator

Application web PWA pour générer des nuages de points 3D depuis des photos.

## ⚡ Démarrage en 3 étapes (GitHub Codespaces)

**Après ouverture du Codespace (setup automatique ~8 min) :**

### Terminal 1 — Backend
```bash
bash start_backend.sh
```

### Terminal 2 — Frontend
```bash
bash start_frontend.sh
```

### Test automatique (optionnel)
```bash
bash run_test.sh
```

## Structure
```
scan3d/
├── .devcontainer/        ← Config GitHub Codespaces (auto-install)
│   ├── devcontainer.json
│   └── setup.sh
├── backend/
│   ├── main.py           ← API FastAPI + pipeline SfM complet
│   ├── requirements.txt
│   └── test_pipeline.py  ← Test avec images synthétiques
├── frontend/
│   └── index.html        ← PWA (WebRTC + viewer Three.js)
├── start_backend.sh      ← Lance le backend (port 8000)
├── start_frontend.sh     ← Lance le frontend (port 3000)
└── run_test.sh           ← Test automatique pipeline
```

## Technologies
- **Backend** : FastAPI + Open3D + OpenCV (ORB features, Essential Matrix, triangulation)
- **Frontend** : Vanilla JS + Three.js (WebRTC caméra, viewer 3D, drag&drop)
- **Export** : PLY binaire ou XYZ ASCII avec couleurs RGB

## Précision attendue
| Conditions | Précision |
|---|---|
| 10 images, simple | 5–10 cm |
| 20–30 images, bon recouvrement | 2–5 cm |
| 50+ images, orbite complète | 1–3 cm |

## Licence
MIT — 100% open-source
