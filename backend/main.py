"""
SCAN3D — Backend FastAPI
Pipeline: ORB features → Essential Matrix → Triangulation → Open3D cleanup → PLY/XYZ export
"""

import os, uuid, shutil, logging, asyncio
from pathlib import Path
from typing import Optional

import numpy as np
import open3d as o3d
import cv2
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger(__name__)

app = FastAPI(title="SCAN3D API", version="1.0.0")

# CORS — allow all (needed for Codespaces dynamic URLs)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR   = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

app.mount("/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")

# In-memory job store
jobs: dict = {}


# ══════════════════════════════════════════════════════════════
#  3D RECONSTRUCTION PIPELINE
# ══════════════════════════════════════════════════════════════

class SfMPipeline:

    def __init__(self):
        self.images: list[np.ndarray] = []
        self.K: Optional[np.ndarray] = None
        self.pcd: Optional[o3d.geometry.PointCloud] = None

    def load_images(self, paths: list[Path]):
        for p in paths:
            img = cv2.imread(str(p))
            if img is not None:
                self.images.append(img)
        log.info(f"Loaded {len(self.images)} images")
        if len(self.images) < 2:
            raise ValueError("Besoin d'au moins 2 images valides")

    def estimate_intrinsics(self):
        h, w = self.images[0].shape[:2]
        f = max(w, h) * 1.2
        self.K = np.array([[f,0,w/2],[0,f,h/2],[0,0,1]], dtype=np.float64)
        log.info(f"Intrinsics: f={f:.1f}, {w}x{h}")

    def _match_pair(self, img1, img2):
        orb = cv2.ORB_create(nfeatures=4000, scaleFactor=1.2, nlevels=8)
        g1  = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
        g2  = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
        kp1, d1 = orb.detectAndCompute(g1, None)
        kp2, d2 = orb.detectAndCompute(g2, None)
        if d1 is None or d2 is None or len(d1) < 10:
            return None, None
        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
        raw = bf.knnMatch(d1, d2, k=2)
        good = [m for m,n in raw if m.distance < 0.75*n.distance]
        if len(good) < 8:
            return None, None
        p1 = np.float32([kp1[m.queryIdx].pt for m in good])
        p2 = np.float32([kp2[m.trainIdx].pt for m in good])
        return p1, p2

    def _recover_pose(self, p1, p2):
        E, mask = cv2.findEssentialMat(p1, p2, self.K,
                                        method=cv2.RANSAC, prob=0.999, threshold=1.0)
        if E is None:
            return None, None, None, None
        _, R, t, mask2 = cv2.recoverPose(E, p1, p2, self.K, mask=mask)
        inl1 = p1[mask2.ravel()==255]
        inl2 = p2[mask2.ravel()==255]
        return R, t, inl1, inl2

    def _triangulate(self, R1, t1, R2, t2, p1, p2):
        P1 = self.K @ np.hstack([R1, t1])
        P2 = self.K @ np.hstack([R2, t2])
        pts4 = cv2.triangulatePoints(P1, P2, p1.T, p2.T)
        pts3 = (pts4[:3] / pts4[3]).T
        valid = pts4[2] * pts4[3] > 0
        return pts3[valid], p1[valid]

    def reconstruct(self):
        all_pts, all_col = [], []
        R_prev = np.eye(3)
        t_prev = np.zeros((3,1))

        for i in range(len(self.images)-1):
            img1, img2 = self.images[i], self.images[i+1]
            p1, p2 = self._match_pair(img1, img2)
            if p1 is None:
                log.warning(f"Pair {i}→{i+1}: no matches")
                continue
            R, t, inl1, inl2 = self._recover_pose(p1, p2)
            if R is None:
                continue
            pts3, used_p1 = self._triangulate(R_prev, t_prev, R, t, inl1, inl2)
            log.info(f"Pair {i}→{i+1}: {len(pts3)} points")

            h, w = img1.shape[:2]
            cols = []
            for pt in used_p1[:len(pts3)]:
                px = int(np.clip(pt[0], 0, w-1))
                py = int(np.clip(pt[1], 0, h-1))
                bgr = img1[py, px] / 255.0
                cols.append(bgr[::-1])  # BGR→RGB

            n = min(len(pts3), len(cols))
            if n > 0:
                all_pts.append(pts3[:n])
                all_col.append(np.array(cols[:n]))

            R_prev = R @ R_prev
            t_prev = R @ t_prev + t

        if not all_pts:
            raise ValueError("Reconstruction échouée — pas assez de correspondances entre images")

        pts = np.vstack(all_pts)
        col = np.clip(np.vstack(all_col), 0, 1)

        self.pcd = o3d.geometry.PointCloud()
        self.pcd.points = o3d.utility.Vector3dVector(pts)
        self.pcd.colors = o3d.utility.Vector3dVector(col)
        log.info(f"Raw cloud: {len(pts)} points")

    def clean(self, voxel: float = 0.02):
        self.pcd, _ = self.pcd.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)
        self.pcd, _ = self.pcd.remove_radius_outlier(nb_points=10, radius=0.1)
        self.pcd = self.pcd.voxel_down_sample(voxel_size=voxel)
        self.pcd.estimate_normals(
            search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.1, max_nn=30)
        )
        log.info(f"Cleaned cloud: {len(self.pcd.points)} points")

    def export_ply(self, path: Path):
        o3d.io.write_point_cloud(str(path), self.pcd, write_ascii=False)

    def export_xyz(self, path: Path):
        pts = np.asarray(self.pcd.points)
        col = (np.asarray(self.pcd.colors)*255).astype(np.uint8)
        data = np.hstack([pts, col])
        np.savetxt(str(path), data, fmt="%.6f %.6f %.6f %d %d %d",
                   header="X Y Z R G B", comments="")

    def stats(self) -> dict:
        if not self.pcd:
            return {}
        pts = np.asarray(self.pcd.points)
        dims = pts.max(axis=0) - pts.min(axis=0)
        return {
            "num_points": len(pts),
            "bbox_m": {
                "width":  round(float(dims[0]),3),
                "depth":  round(float(dims[1]),3),
                "height": round(float(dims[2]),3),
            }
        }


# ══════════════════════════════════════════════════════════════
#  API ENDPOINTS
# ══════════════════════════════════════════════════════════════

@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    return jobs[job_id]


@app.post("/reconstruct")
async def reconstruct(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    export_format: str = "ply",
    voxel_size: float = 0.02,
):
    if len(files) < 2:
        raise HTTPException(400, "Minimum 2 images requises")
    if len(files) > 60:
        raise HTTPException(400, "Maximum 60 images")

    job_id = str(uuid.uuid4())[:8]
    session = UPLOAD_DIR / job_id
    session.mkdir()

    saved = []
    for f in files:
        ext  = Path(f.filename).suffix.lower() or ".jpg"
        dest = session / f"{uuid.uuid4().hex}{ext}"
        content = await f.read()
        dest.write_bytes(content)
        saved.append(dest)

    jobs[job_id] = {"status": "queued", "progress": 0, "job_id": job_id}
    background_tasks.add_task(_pipeline_task, job_id, session, saved, export_format, voxel_size)
    return {"job_id": job_id, "num_images": len(files)}


async def _pipeline_task(job_id, session, paths, fmt, voxel):
    jobs[job_id]["status"] = "running"
    try:
        pipe = SfMPipeline()

        jobs[job_id]["progress"] = 10
        await asyncio.to_thread(pipe.load_images, paths)

        jobs[job_id]["progress"] = 20
        await asyncio.to_thread(pipe.estimate_intrinsics)

        jobs[job_id]["progress"] = 40
        await asyncio.to_thread(pipe.reconstruct)

        jobs[job_id]["progress"] = 75
        await asyncio.to_thread(pipe.clean, voxel)

        jobs[job_id]["progress"] = 90
        out_name = f"pointcloud_{job_id}"
        if fmt == "xyz":
            out = OUTPUT_DIR / f"{out_name}.xyz"
            await asyncio.to_thread(pipe.export_xyz, out)
        else:
            out = OUTPUT_DIR / f"{out_name}.ply"
            await asyncio.to_thread(pipe.export_ply, out)

        jobs[job_id].update({
            "status": "done",
            "progress": 100,
            "download_url": f"/outputs/{out.name}",
            "stats": pipe.stats(),
        })
        log.info(f"Job {job_id} done — {pipe.stats()}")

    except Exception as e:
        log.exception(f"Job {job_id} failed")
        jobs[job_id] = {"status": "error", "error": str(e), "job_id": job_id}
    finally:
        shutil.rmtree(session, ignore_errors=True)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
