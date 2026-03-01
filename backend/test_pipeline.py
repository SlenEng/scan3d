"""
Test automatique du pipeline SCAN3D
Génère des images synthétiques et teste la reconstruction complète.
Usage: python test_pipeline.py
"""

import sys, time, shutil, tempfile
from pathlib import Path
import numpy as np
import cv2
import requests

API = "http://localhost:8000"

def make_images(n=10):
    """Génère n images synthétiques d'une scène intérieure."""
    tmp = Path(tempfile.mkdtemp())
    paths = []
    w, h = 640, 480

    for i in range(n):
        img = np.zeros((h, w, 3), dtype=np.uint8)
        angle = np.radians(i * 360/n)
        vx = w//2 + int(60*np.sin(angle))
        vy = h//2 + int(20*np.cos(angle*0.7))

        # Sol
        cv2.fillPoly(img, [np.array([[0,h],[w,h],[vx+130,h//2],[vx-130,h//2]])], (55,50,45))
        # Mur du fond
        cv2.fillPoly(img, [np.array([[vx-130,h//2],[vx+130,h//2],[vx+180,0],[vx-180,0]])], (175,170,165))
        # Mur gauche
        cv2.fillPoly(img, [np.array([[0,h],[vx-130,h//2],[vx-180,0],[0,0]])], (145,140,135))
        # Mur droit
        cv2.fillPoly(img, [np.array([[w,h],[vx+130,h//2],[vx+180,0],[w,0]])], (155,150,145))

        # Grille de points (features pour ORB)
        for row in range(0, 10):
            for col in range(0, 14):
                if (row+col)%2 == 0:
                    fx = vx-120 + col*16 + int(4*np.sin(angle))
                    fy = h//2 - 5  + row*16
                    cv2.rectangle(img, (fx,fy), (fx+12,fy+12), (70,70,70), -1)

        # Fenêtre
        wx = vx - 25 + int(8*np.cos(angle))
        cv2.rectangle(img, (wx, h//2+20), (wx+50,h//2+70), (190,210,245), -1)
        cv2.rectangle(img, (wx, h//2+20), (wx+50,h//2+70), (110,110,110), 2)

        # Bruit
        noise = np.random.normal(0, 6, img.shape).astype(np.int16)
        img = np.clip(img.astype(np.int16)+noise, 0, 255).astype(np.uint8)

        p = tmp / f"frame_{i:04d}.jpg"
        cv2.imwrite(str(p), img, [cv2.IMWRITE_JPEG_QUALITY, 95])
        paths.append(p)

    print(f"  ✓ {n} images générées dans {tmp}")
    return paths, tmp


def run():
    print("\n╔══════════════════════════════════════════╗")
    print("║   SCAN3D — Test Pipeline Automatique    ║")
    print("╚══════════════════════════════════════════╝\n")

    # 1. API health
    print("[1/5] Vérification API...")
    try:
        r = requests.get(f"{API}/health", timeout=5)
        r.raise_for_status()
        print(f"  ✓ API en ligne: {r.json()}")
    except Exception as e:
        print(f"  ✗ API inaccessible: {e}")
        print("  → Lancez d'abord: bash start_backend.sh")
        sys.exit(1)

    # 2. Génération images
    print("\n[2/5] Génération des images de test...")
    paths, tmp = make_images(n=10)

    # 3. Upload
    print("\n[3/5] Upload vers /reconstruct...")
    files = [('files', (p.name, open(p,'rb'), 'image/jpeg')) for p in paths]
    data  = {'voxel_size':'0.02', 'export_format':'ply'}
    try:
        r = requests.post(f"{API}/reconstruct", files=files, data=data, timeout=30)
        [f[1][1].close() for f in files]
        r.raise_for_status()
        job_id = r.json()['job_id']
        print(f"  ✓ Job créé: {job_id}")
    except Exception as e:
        print(f"  ✗ Upload échoué: {e}")
        sys.exit(1)

    # 4. Polling
    print("\n[4/5] Reconstruction en cours...")
    for sec in range(180):
        time.sleep(1.5)
        job = requests.get(f"{API}/jobs/{job_id}", timeout=5).json()
        pct = job.get('progress', 0)
        bar = '█'*(pct//5) + '░'*(20-pct//5)
        status = job.get('status','...')
        print(f"\r  [{bar}] {pct:3d}%  {status:<30}", end='', flush=True)

        if status == 'done':
            print(f"\n  ✓ Terminé en ~{int(sec*1.5)}s")
            break
        elif status == 'error':
            print(f"\n  ✗ Erreur: {job.get('error','?')}")
            sys.exit(1)
    else:
        print("\n  ✗ Timeout (3 min)")
        sys.exit(1)

    # 5. Résultats
    print("\n[5/5] Résultats:")
    st = job.get('stats', {})
    bb = st.get('bbox_m', {})
    print(f"  Points     : {st.get('num_points',0):,}")
    print(f"  Bbox (m)   : {bb.get('width','?')} x {bb.get('depth','?')} x {bb.get('height','?')}")
    print(f"  Télécharger: {API}{job.get('download_url','')}")

    # Download check
    dl_url = API + job.get('download_url','')
    dl = requests.get(dl_url, timeout=30)
    kb = len(dl.content)//1024
    print(f"  Taille     : {kb} KB")

    ok = st.get('num_points',0) > 50
    print(f"\n{'✅ TEST RÉUSSI' if ok else '⚠️  Peu de points — vérifiez les images'}\n")

    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(run())
