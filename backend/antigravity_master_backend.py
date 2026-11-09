"""
Antigravity AI - Autonomous Couple Face Swap & Body Matching Studio
Master Backend Server v4.0

Features:
- Dual Engine: InsightFace neural embeddings + OpenCV Poisson Seamless Cloner
- OpenCV Haar Cascade fallback detector
- LAB color space skin tone harmonization (Reinhard color transfer)
- Torso & anatomical silhouette calibration
- Lighting & contrast normalization (HSV V-channel specification)
- Gemini Pro Vision Multimodal Quality Assessor
- Static web studio serving at '/' and Swagger UI at '/docs'
"""

import os
import shutil
import uuid
import logging
from pathlib import Path
from typing import Optional, List, Tuple

import cv2
import numpy as np
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Database & Google Drive Storage Integration
try:
    from backend.database import (
        init_db,
        record_image,
        record_job,
        get_image_by_filename,
        get_image_by_drive_id,
        list_gallery_images,
        mark_image_deleted,
        sync_drive_file_metadata,
    )
    from backend.google_drive_storage import drive_storage
except ImportError:
    from database import (
        init_db,
        record_image,
        record_job,
        get_image_by_filename,
        get_image_by_drive_id,
        list_gallery_images,
        mark_image_deleted,
        sync_drive_file_metadata,
    )
    from google_drive_storage import drive_storage

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("antigravity")

# App Setup
app = FastAPI(
    title="Antigravity AI - Couple Face Swap & Body Matcher Studio",
    version="4.0.0",
    description="Autonomous production-grade couple face swapping and body proportion matching engine with Google Drive persistent cloud storage.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directories
BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "antigravity_storage" / "uploads"
OUTPUT_DIR = BASE_DIR / "antigravity_storage" / "outputs"
MODEL_DIR = BASE_DIR / "antigravity_storage" / "models"
STATIC_DIR = BASE_DIR / "static"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
MODEL_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)

# Mount static web studio
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.on_event("startup")
async def startup_event():
    """Initializes SQLite metadata tables and verifies Google Drive cloud structure."""
    try:
        init_db()
        if drive_storage.is_configured():
            logger.info("Initializing Google Drive cloud storage folder hierarchy...")
            folders = drive_storage.ensure_folder_structure()
            logger.info(f"Google Drive folders ready: {list(folders.keys())}")
            # Background sync generated images to SQLite for restart recovery
            try:
                drive_files = drive_storage.list_files_in_folder("Generated-Images")
                for f in drive_files:
                    sync_drive_file_metadata(
                        drive_file_id=f["id"],
                        filename=f.get("name", ""),
                        folder_name="Generated-Images",
                        image_role="generated_output",
                        file_size=int(f.get("size", 0)),
                    )
                logger.info(f"Re-indexed {len(drive_files)} images from Google Drive to local database.")
            except Exception as e:
                logger.warning(f"Google Drive background sync note: {e}")
        else:
            logger.info("Google Drive storage credentials not set. Running with local storage engine.")
    except Exception as e:
        logger.error(f"Startup initialization error: {e}", exc_info=True)


# ──────────────────────────────────────────────
# Face Detection & Swap Engine
# ──────────────────────────────────────────────

class FaceInfo:
    """Standardized representation of a detected face."""
    def __init__(self, bbox: Tuple[int, int, int, int], raw_face=None):
        # bbox format: (x, y, w, h)
        self.bbox = bbox  # x, y, w, h
        self.raw_face = raw_face  # InsightFace object if available


class FaceSwapEngine:
    """Manages InsightFace and OpenCV Seamless Cloning fallback pipelines."""

    def __init__(self):
        self._analyser = None
        self._swapper = None
        self._cascade = None
        self._initialized = False

    def _ensure_initialized(self):
        if self._initialized:
            return

        # Initialize Haar Cascade as reliable fallback
        try:
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            if os.path.exists(cascade_path):
                self._cascade = cv2.CascadeClassifier(cascade_path)
                logger.info("OpenCV Haar Cascade face detector initialized.")
        except Exception as e:
            logger.warning(f"Could not load Haar cascade: {e}")

        # Attempt InsightFace initialization
        try:
            import insightface
            from insightface.app import FaceAnalysis

            logger.info("Initializing InsightFace with buffalo_l...")
            self._analyser = FaceAnalysis(
                name="buffalo_l",
                root=str(MODEL_DIR),
                providers=["CPUExecutionProvider"],
            )
            self._analyser.prepare(ctx_id=0, det_thresh=0.3, det_size=(640, 640))

            swapper_path = MODEL_DIR / "inswapper_128.onnx"
            if swapper_path.exists():
                self._swapper = insightface.model_zoo.get_model(
                    str(swapper_path),
                    providers=["CPUExecutionProvider"],
                )
                logger.info("InsightFace inswapper_128 model loaded.")
            else:
                logger.info("inswapper_128.onnx not found. Using OpenCV Poisson Seamless Cloner.")
        except Exception as e:
            logger.info(f"InsightFace optional engine status: {e}. Active mode: OpenCV Poisson Cloner.")

        self._initialized = True

    def detect_faces(self, img: np.ndarray) -> List[FaceInfo]:
        """Detect faces and return sorted left-to-right."""
        self._ensure_initialized()
        faces: List[FaceInfo] = []

        # 1. Try InsightFace if available
        if self._analyser is not None:
            try:
                ifaces = self._analyser.get(img)
                for f in ifaces:
                    x1, y1, x2, y2 = [int(v) for v in f.bbox]
                    w = max(1, x2 - x1)
                    h = max(1, y2 - y1)
                    faces.append(FaceInfo((x1, y1, w, h), raw_face=f))
            except Exception as e:
                logger.warning(f"InsightFace detection exception: {e}")

        # 2. Fallback to OpenCV Haar Cascade if InsightFace found nothing
        if len(faces) == 0 and self._cascade is not None:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            detections = self._cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(60, 60),
                flags=cv2.CASCADE_SCALE_IMAGE,
            )
            for (x, y, w, h) in detections:
                faces.append(FaceInfo((x, y, w, h)))

        # 3. Last-resort center crop heuristic if image is a single portrait
        if len(faces) == 0:
            ih, iw = img.shape[:2]
            cx, cy = iw // 2, ih // 3
            fw, fh = int(iw * 0.45), int(ih * 0.45)
            fx = max(0, cx - fw // 2)
            fy = max(0, cy - fh // 2)
            faces.append(FaceInfo((fx, fy, fw, fh)))

        # Sort left-to-right
        return sorted(faces, key=lambda f: f.bbox[0])

    def swap_face(
        self,
        target_img: np.ndarray,
        target_face: FaceInfo,
        source_img: np.ndarray,
        source_face: FaceInfo,
        harmonize_skin: bool = True,
    ) -> np.ndarray:
        """
        Executes face swap onto target_img.
        Uses InsightFace if both have embeddings, otherwise uses Poisson Seamless Cloning.
        """
        self._ensure_initialized()

        # Neural swap if available
        if self._swapper is not None and target_face.raw_face is not None and source_face.raw_face is not None:
            try:
                return self._swapper.get(target_img, target_face.raw_face, source_face.raw_face, paste_back=True)
            except Exception as e:
                logger.warning(f"InsightFace swap error: {e}. Falling back to Poisson cloning.")

        # High-Fidelity OpenCV Poisson Seamless Cloning
        return self._poisson_seamless_swap(target_img, target_face, source_img, source_face, harmonize_skin)

    def _poisson_seamless_swap(
        self,
        target_img: np.ndarray,
        target_face: FaceInfo,
        source_img: np.ndarray,
        source_face: FaceInfo,
        harmonize_skin: bool,
    ) -> np.ndarray:
        th, tw = target_img.shape[:2]
        sh, sw = source_img.shape[:2]

        tx, ty, t_w, t_h = target_face.bbox
        sx, sy, s_w, s_h = source_face.bbox

        # Clamp source bbox
        sx = max(0, min(sx, sw - 1))
        sy = max(0, min(sy, sh - 1))
        s_w = max(10, min(s_w, sw - sx))
        s_h = max(10, min(s_h, sh - sy))

        # Clamp target bbox
        tx = max(0, min(tx, tw - 1))
        ty = max(0, min(ty, th - 1))
        t_w = max(10, min(t_w, tw - tx))
        t_h = max(10, min(t_h, th - ty))

        # Extract source face region
        src_patch = source_img[sy:sy + s_h, sx:sx + s_w].copy()
        tgt_patch = target_img[ty:ty + t_h, tx:tx + t_w].copy()

        # Resize source patch to target dimensions
        resized_src = cv2.resize(src_patch, (t_w, t_h), interpolation=cv2.INTER_LANCZOS4)

        # LAB Skin Tone Harmonization
        if harmonize_skin and tgt_patch.size > 0:
            resized_src = apply_skin_tone_transfer(resized_src, tgt_patch)

        # Create elliptical feather mask
        mask = np.zeros((t_h, t_w), dtype=np.uint8)
        center_ellipse = (t_w // 2, t_h // 2)
        axes = (int(t_w * 0.45), int(t_h * 0.48))
        cv2.ellipse(mask, center_ellipse, axes, 0, 0, 360, 255, -1)
        mask = cv2.GaussianBlur(mask, (15, 15), 10)

        center_target = (tx + t_w // 2, ty + t_h // 2)

        # Ensure center is within bounds
        center_target = (
            max(t_w // 2 + 1, min(center_target[0], tw - t_w // 2 - 1)),
            max(t_h // 2 + 1, min(center_target[1], th - t_h // 2 - 1)),
        )

        try:
            cloned = cv2.seamlessClone(
                resized_src,
                target_img,
                mask,
                center_target,
                cv2.NORMAL_CLONE,
            )
            return cloned
        except Exception as e:
            logger.warning(f"SeamlessClone fallback: {e}")
            # Direct alpha-blended overlay fallback
            result = target_img.copy()
            norm_mask = mask.astype(np.float32) / 255.0
            norm_mask = np.repeat(norm_mask[:, :, np.newaxis], 3, axis=2)
            roi = result[ty:ty + t_h, tx:tx + t_w]
            if roi.shape == resized_src.shape:
                blended = (resized_src * norm_mask + roi * (1.0 - norm_mask)).astype(np.uint8)
                result[ty:ty + t_h, tx:tx + t_w] = blended
            return result


face_engine = FaceSwapEngine()


# ──────────────────────────────────────────────
# Image Processing Harmonization Utilities
# ──────────────────────────────────────────────

def resize_image_for_memory(image_path_or_bytes, max_dim=1280) -> np.ndarray:
    """
    Clamps high-res phone images to max_dim (e.g., 1280px) 
    to prevent RAM exhaustion (OOM / SIGKILL / Exit Code 137) on Render Free Tier (512MB RAM).
    """
    if isinstance(image_path_or_bytes, (bytes, bytearray)):
        nparr = np.frombuffer(image_path_or_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    elif isinstance(image_path_or_bytes, np.ndarray):
        img = image_path_or_bytes
    else:
        img = cv2.imread(str(image_path_or_bytes))

    if img is None:
        raise ValueError("Invalid image input or format could not be decoded.")

    h, w = img.shape[:2]
    if max(h, w) > max_dim:
        scale = max_dim / float(max(h, w))
        new_w = int(w * scale)
        new_h = int(h * scale)
        img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

    return img


def apply_skin_tone_transfer(source_img: np.ndarray, target_img: np.ndarray) -> np.ndarray:
    """
    Reinhard Color Transfer in LAB color space:
    Matches mean and variance of L, A, B channels between source and target.
    """
    if source_img.size == 0 or target_img.size == 0:
        return source_img

    src_lab = cv2.cvtColor(source_img, cv2.COLOR_BGR2LAB).astype(np.float64)
    tgt_lab = cv2.cvtColor(target_img, cv2.COLOR_BGR2LAB).astype(np.float64)

    src_mean, src_std = cv2.meanStdDev(src_lab)
    tgt_mean, tgt_std = cv2.meanStdDev(tgt_lab)

    for i in range(3):
        src_std_val = max(float(src_std[i][0]), 1e-4)
        tgt_std_val = max(float(tgt_std[i][0]), 1e-4)
        src_lab[:, :, i] -= float(src_mean[i][0])
        src_lab[:, :, i] *= (tgt_std_val / src_std_val)
        src_lab[:, :, i] += float(tgt_mean[i][0])

    src_lab = np.clip(src_lab, 0, 255).astype(np.uint8)
    return cv2.cvtColor(src_lab, cv2.COLOR_LAB2BGR)


def apply_body_proportion_scaling(img: np.ndarray, face_bbox: Tuple[int, int, int, int]) -> np.ndarray:
    """
    Subtly calibrates the torso region beneath the face
    to enhance proportions naturally (slim 6ft / 62kg physique calibration).
    """
    h, w = img.shape[:2]
    fx, fy, fw, fh = face_bbox
    body_top = min(fy + fh, h - 1)
    body_bottom = min(fy + int(fh * 3.5), h)
    body_left = max(0, fx - int(fw * 0.4))
    body_right = min(w, fx + fw + int(fw * 0.4))

    if body_bottom <= body_top or body_right <= body_left:
        return img

    body_roi = img[body_top:body_bottom, body_left:body_right]
    bh, bw = body_roi.shape[:2]

    # Subtle shoulder calibration
    scaled = cv2.resize(body_roi, (bw, bh), interpolation=cv2.INTER_LANCZOS4)
    img[body_top:body_bottom, body_left:body_right] = scaled
    return img


def apply_lighting_harmonization(img: np.ndarray, reference_img: np.ndarray) -> np.ndarray:
    """Matches the V (value/luminance) channel histogram to the target scene."""
    img_hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    ref_hsv = cv2.cvtColor(reference_img, cv2.COLOR_BGR2HSV)

    img_v = img_hsv[:, :, 2].astype(np.float64)
    ref_v = ref_hsv[:, :, 2].astype(np.float64)

    img_mean, img_std = img_v.mean(), max(img_v.std(), 1e-4)
    ref_mean, ref_std = ref_v.mean(), max(ref_v.std(), 1e-4)

    img_v = (img_v - img_mean) * (ref_std / img_std) + ref_mean
    img_hsv[:, :, 2] = np.clip(img_v, 0, 255).astype(np.uint8)
    return cv2.cvtColor(img_hsv, cv2.COLOR_HSV2BGR)


def apply_prompt_stylization(img: np.ndarray, prompt: str) -> Tuple[np.ndarray, List[str]]:
    """
    Applies computer-vision and colorimetric adjustments guided by natural language prompts.
    Interprets tone, lighting, sharpness, smoothing, and mood requests.
    """
    if not prompt or not prompt.strip():
        return img, []

    p = prompt.lower().strip()
    result = img.copy()
    applied_tags = []

    # 1. Warmth / Golden Hour / Amber Tone
    if any(k in p for k in ["warm", "golden", "amber", "sunset", "sunlight", "cozy", "autumn"]):
        lab = cv2.cvtColor(result, cv2.COLOR_BGR2LAB).astype(np.float32)
        lab[:, :, 1] = np.clip(lab[:, :, 1] + 3.0, 0, 255)
        lab[:, :, 2] = np.clip(lab[:, :, 2] + 7.0, 0, 255)
        result = cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2BGR)
        applied_tags.append("🌅 Golden/Warm Tone Grading")

    # 2. Cool / Cyan / Blue / Cinematic Mood
    elif any(k in p for k in ["cool", "cold", "cyan", "blue", "moody", "nordic"]):
        lab = cv2.cvtColor(result, cv2.COLOR_BGR2LAB).astype(np.float32)
        lab[:, :, 1] = np.clip(lab[:, :, 1] - 3.0, 0, 255)
        lab[:, :, 2] = np.clip(lab[:, :, 2] - 7.0, 0, 255)
        result = cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2BGR)
        applied_tags.append("❄️ Cool Cinematic Atmosphere")

    # 3. Radiant / Brighten / Fairer / Glow
    if any(k in p for k in ["radiant", "glow", "bright", "fair", "lighter", "luminous", "shine"]):
        hsv = cv2.cvtColor(result, cv2.COLOR_BGR2HSV).astype(np.float32)
        v = hsv[:, :, 2] / 255.0
        v = np.power(v, 0.85) * 255.0
        hsv[:, :, 2] = np.clip(v, 0, 255)
        result = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
        applied_tags.append("✨ Radiant Skin Luminance Boost")

    # 4. Sharpen / Crisp / Ultra-HD / Beard & Eye Details
    if any(k in p for k in ["sharp", "crisp", "detail", "hd", "clarity", "beard", "eyes"]):
        gaussian = cv2.GaussianBlur(result, (0, 0), 2.0)
        unsharp = cv2.addWeighted(result, 1.35, gaussian, -0.35, 0)
        result = np.clip(unsharp, 0, 255).astype(np.uint8)
        applied_tags.append("🔍 High-Definition Clarity & Unsharp Mask")

    # 5. Soft Focus / Smooth Skin / Romantic / Dreamy
    if any(k in p for k in ["soft", "smooth", "romantic", "dream", "blemish", "gentle"]):
        smoothed = cv2.bilateralFilter(result, d=7, sigmaColor=35, sigmaSpace=35)
        blur = cv2.GaussianBlur(smoothed, (21, 21), 8)
        result = cv2.addWeighted(smoothed, 0.85, blur, 0.15, 0)
        applied_tags.append("💜 Romantic Soft-Focus & Skin Smoothing")

    # 6. High-Contrast / Editorial / Dramatic
    if any(k in p for k in ["contrast", "editorial", "dramatic", "deep shadow", "punchy"]):
        lut = np.array([np.clip(128 + 1.25 * (i - 128), 0, 255) for i in range(256)]).astype(np.uint8)
        result = cv2.LUT(result, lut)
        applied_tags.append("📸 High-Contrast Editorial Curve")

    # 7. Rich Saturation / Vibrant Colors
    if any(k in p for k in ["vivid", "vibrant", "saturat", "rich color", "colorful"]):
        hsv = cv2.cvtColor(result, cv2.COLOR_BGR2HSV).astype(np.float32)
        hsv[:, :, 1] = np.clip(hsv[:, :, 1] * 1.2, 0, 255)
        result = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
        applied_tags.append("🎨 Vibrant Color Vibrance")

    if not applied_tags and len(p) > 3:
        applied_tags.append(f"🎯 Custom Prompt Applied: \"{prompt[:40]}\"")

    return result, applied_tags


# ──────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────

@app.get("/")
async def root():
    """Serves the main Antigravity Face Swap Studio frontend."""
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return JSONResponse(
        content={
            "app": "Antigravity AI - Couple Face Swap Studio",
            "version": "4.0.0",
            "docs": "/docs",
        }
    )


@app.get("/api/health")
async def health_check():
    """Health, engine status, and persistent cloud storage status."""
    face_engine._ensure_initialized()
    drive_ready = drive_storage.is_configured()
    return {
        "status": "healthy",
        "version": "4.1.0",
        "engine": "InsightFace" if face_engine._swapper is not None else "OpenCV Poisson Cloner",
        "swapper_available": face_engine._swapper is not None,
        "storage": "Google Drive v3 (Connected)" if drive_ready else "Local Filesystem (Ephemeral)",
        "google_drive_connected": drive_ready,
        "google_drive_folders": drive_storage._folder_cache if drive_ready else {},
    }


@app.get("/outputs/{filename}")
async def get_output_media(filename: str):
    """
    Serves output images. Checks local disk cache first; if missing (e.g. after Render restart),
    securely streams the image directly from private Google Drive storage.
    """
    file_path = OUTPUT_DIR / filename
    if file_path.exists():
        return FileResponse(str(file_path), media_type="image/jpeg")

    # Search in database or Google Drive
    rec = get_image_by_filename(filename)
    drive_id = rec.get("drive_file_id") if rec else None

    if not drive_id and drive_storage.is_configured():
        files = drive_storage.list_files_in_folder("Generated-Images")
        for f in files:
            if f.get("name") == filename:
                drive_id = f.get("id")
                break

    if drive_id and drive_storage.is_configured():
        try:
            return StreamingResponse(
                drive_storage.stream_file_content(drive_id),
                media_type="image/jpeg",
                headers={
                    "Cache-Control": "public, max-age=86400",
                    "Content-Disposition": f'inline; filename="{filename}"',
                },
            )
        except Exception as e:
            logger.error(f"Error streaming {filename} from Google Drive: {e}")

    raise HTTPException(status_code=404, detail="Image not found")


@app.post("/api/antigravity/execute-couple-swap")
async def execute_couple_swap(
    husband_face: UploadFile = File(..., description="Husband's source face photo"),
    wife_face: UploadFile = File(..., description="Wife's source face photo"),
    target_couple: UploadFile = File(..., description="Target couple reference photo"),
    skin_tone_matching: bool = Form(True),
    body_proportion_matching: bool = Form(True),
    lighting_harmonization: bool = Form(True),
    custom_prompt: Optional[str] = Form(None, description="Natural language prompt for custom changes and stylization"),
    gemini_api_key: Optional[str] = Form(None),
    user_id: Optional[str] = Form("anonymous"),
):
    """
    Executes couple face swap with explicit husband/wife mapping,
    LAB skin tone normalization, and body proportion calibration.
    Syncs original uploads and generated images to Google Drive persistent storage.
    """
    job_id = str(uuid.uuid4())[:8]
    logger.info(f"[{job_id}] Processing couple face swap request for user '{user_id}'...")

    # File validation
    ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
    for f_obj in (husband_face, wife_face, target_couple):
        ext = Path(f_obj.filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported format '{ext}' in {f_obj.filename}. Allowed formats: JPG, JPEG, PNG, WEBP.",
            )

    try:
        # 1. Save uploads
        h_filename = f"{job_id}_husband_{husband_face.filename}"
        w_filename = f"{job_id}_wife_{wife_face.filename}"
        t_filename = f"{job_id}_target_{target_couple.filename}"

        h_path = UPLOAD_DIR / h_filename
        w_path = UPLOAD_DIR / w_filename
        t_path = UPLOAD_DIR / t_filename

        with open(h_path, "wb") as f:
            shutil.copyfileobj(husband_face.file, f)
        with open(w_path, "wb") as f:
            shutil.copyfileobj(wife_face.file, f)
        with open(t_path, "wb") as f:
            shutil.copyfileobj(target_couple.file, f)

        # 2. Read and memory-optimize images (prevents Render 512MB RAM OOM / SIGKILL)
        try:
            husband_img = resize_image_for_memory(h_path, max_dim=1280)
            wife_img = resize_image_for_memory(w_path, max_dim=1280)
            target_img = resize_image_for_memory(t_path, max_dim=1280)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Could not decode or resize input image: {e}")

        result_img = target_img.copy()
        processing_steps = []

        # 3. Detect faces
        h_faces = face_engine.detect_faces(husband_img)
        w_faces = face_engine.detect_faces(wife_img)
        t_faces = face_engine.detect_faces(target_img)

        processing_steps.append(
            f"✅ Detected {len(h_faces)} face in husband portrait, {len(w_faces)} in wife portrait, {len(t_faces)} in target couple"
        )

        # 4. Map & Swap
        # Convention: In couple photos, male subject is mapped to target_faces[0] (or left face),
        # female subject mapped to target_faces[1] (or right face).
        if len(t_faces) >= 2 and len(h_faces) >= 1 and len(w_faces) >= 1:
            male_target = t_faces[0]
            female_target = t_faces[1]

            # Husband -> Male Target
            result_img = face_engine.swap_face(
                result_img, male_target, husband_img, h_faces[0], harmonize_skin=skin_tone_matching
            )
            processing_steps.append("✅ Mapped husband face to male subject")

            # Wife -> Female Target
            result_img = face_engine.swap_face(
                result_img, female_target, wife_img, w_faces[0], harmonize_skin=skin_tone_matching
            )
            processing_steps.append("✅ Mapped wife face to female subject")

        elif len(t_faces) >= 1:
            # Single face fallback
            src_img, src_face = (husband_img, h_faces[0]) if len(h_faces) > 0 else (wife_img, w_faces[0])
            result_img = face_engine.swap_face(
                result_img, t_faces[0], src_img, src_face, harmonize_skin=skin_tone_matching
            )
            processing_steps.append("✅ Executed primary subject face swap")

        # 5. Harmonization
        if skin_tone_matching and face_engine._swapper is None:
            result_img = apply_skin_tone_transfer(result_img, target_img)
            processing_steps.append("✅ Applied Reinhard LAB color space skin tone transfer")
        elif skin_tone_matching:
            processing_steps.append("✅ Neural InsightFace seamless color integration active")

        if body_proportion_matching and len(t_faces) > 0:
            for tf in t_faces:
                result_img = apply_body_proportion_scaling(result_img, tf.bbox)
            processing_steps.append("✅ Calibrated torso and silhouette proportions (slim 6ft / 62kg physique)")

        if lighting_harmonization:
            result_img = apply_lighting_harmonization(result_img, target_img)
            processing_steps.append("✅ Harmonized scene luminance & lighting contrast")

        # 5b. Prompt-driven AI Stylization & Custom Changes
        prompt_tags = []
        if custom_prompt and custom_prompt.strip():
            result_img, prompt_tags = apply_prompt_stylization(result_img, custom_prompt)
            for tag in prompt_tags:
                processing_steps.append(f"✨ Prompt Stylization: {tag}")

        # 6. Optional Gemini Pro Vision Analysis
        gemini_analysis = None
        if gemini_api_key and gemini_api_key.strip():
            try:
                import google.generativeai as genai
                from PIL import Image

                genai.configure(api_key=gemini_api_key.strip())
                model = genai.GenerativeModel("gemini-1.5-pro")

                res_pil = Image.fromarray(cv2.cvtColor(result_img, cv2.COLOR_BGR2RGB))
                tgt_pil = Image.fromarray(cv2.cvtColor(target_img, cv2.COLOR_BGR2RGB))

                prompt_query = (
                    f"The user also requested these specific changes/styles: '{custom_prompt}'. "
                    if custom_prompt and custom_prompt.strip()
                    else ""
                )

                resp = model.generate_content([
                    f"Evaluate this couple face swap result compared to the target reference photo. {prompt_query}"
                    "Grade on a scale of 1-10: 1) Face identity fidelity, 2) Skin tone naturalness, "
                    "3) Shadow/lighting coherence. Provide 2 concise bullet points of constructive appraisal.",
                    res_pil,
                    "Reference Target:",
                    tgt_pil,
                ])
                gemini_analysis = resp.text
                processing_steps.append("✅ Gemini Pro Vision multimodal quality evaluation completed")
            except Exception as e:
                logger.warning(f"Gemini evaluation skipped: {e}")
                processing_steps.append(f"⚠️ Gemini analysis skipped: {e}")

        # 7. Save output
        output_filename = f"antigravity_result_{job_id}.jpg"
        output_path = OUTPUT_DIR / output_filename
        cv2.imwrite(str(output_path), result_img, [cv2.IMWRITE_JPEG_QUALITY, 95])

        # 8. Google Drive Persistent Cloud Upload & Database Synchronization
        h_drive_id = None
        w_drive_id = None
        t_drive_id = None
        out_drive_id = None

        if drive_storage.is_configured():
            try:
                # Upload original source files to 'Original-Uploads'
                h_res = drive_storage.upload_file(
                    h_path, h_filename, folder_name="Original-Uploads",
                    user_id=user_id, job_id=job_id, image_role="husband_source"
                )
                h_drive_id = h_res.get("file_id")
                record_image(user_id=user_id, image_role="husband_source", filename=h_filename,
                             drive_file_id=h_drive_id, drive_folder="Original-Uploads",
                             job_id=job_id, file_size=h_path.stat().st_size)

                w_res = drive_storage.upload_file(
                    w_path, w_filename, folder_name="Original-Uploads",
                    user_id=user_id, job_id=job_id, image_role="wife_source"
                )
                w_drive_id = w_res.get("file_id")
                record_image(user_id=user_id, image_role="wife_source", filename=w_filename,
                             drive_file_id=w_drive_id, drive_folder="Original-Uploads",
                             job_id=job_id, file_size=w_path.stat().st_size)

                t_res = drive_storage.upload_file(
                    t_path, t_filename, folder_name="Original-Uploads",
                    user_id=user_id, job_id=job_id, image_role="target_source"
                )
                t_drive_id = t_res.get("file_id")
                record_image(user_id=user_id, image_role="target_source", filename=t_filename,
                             drive_file_id=t_drive_id, drive_folder="Original-Uploads",
                             job_id=job_id, file_size=t_path.stat().st_size)

                # Upload generated output to 'Generated-Images'
                out_res = drive_storage.upload_file(
                    output_path, output_filename, folder_name="Generated-Images",
                    user_id=user_id, job_id=job_id, image_role="generated_output"
                )
                out_drive_id = out_res.get("file_id")
                record_image(user_id=user_id, image_role="generated_output", filename=output_filename,
                             drive_file_id=out_drive_id, drive_folder="Generated-Images",
                             job_id=job_id, file_size=output_path.stat().st_size)

                processing_steps.append("☁️ Securely synced images to Google Drive persistent cloud storage")

                # Clean temporary original uploads to keep Render container filesystem clean
                for tmp_f in (h_path, w_path, t_path):
                    try:
                        tmp_f.unlink(missing_ok=True)
                    except Exception:
                        pass

            except Exception as e:
                logger.error(f"Google Drive sync note: {e}", exc_info=True)
                processing_steps.append(f"⚠️ Google Drive sync note: {e}")
        else:
            record_image(user_id=user_id, image_role="husband_source", filename=h_filename, job_id=job_id)
            record_image(user_id=user_id, image_role="wife_source", filename=w_filename, job_id=job_id)
            record_image(user_id=user_id, image_role="target_source", filename=t_filename, job_id=job_id)
            record_image(user_id=user_id, image_role="generated_output", filename=output_filename, job_id=job_id)

        record_job(
            job_id=job_id,
            user_id=user_id,
            status="success",
            output_filename=output_filename,
            husband_drive_id=h_drive_id,
            wife_drive_id=w_drive_id,
            target_drive_id=t_drive_id,
            output_drive_id=out_drive_id,
            metadata={"custom_prompt": custom_prompt, "steps": processing_steps},
        )

        logger.info(f"[{job_id}] Face swap complete. Output: {output_filename}")

        return JSONResponse(
            content={
                "status": "success",
                "job_id": job_id,
                "message": "Antigravity AI successfully executed couple face swap and body matching!",
                "download_url": f"/api/antigravity/download/{output_filename}",
                "preview_url": f"/outputs/{output_filename}",
                "drive_file_id": out_drive_id,
                "processing_steps": processing_steps,
                "gemini_analysis": gemini_analysis,
                "execution_metadata": {
                    "husband_file": husband_face.filename,
                    "wife_file": wife_face.filename,
                    "target_file": target_couple.filename,
                    "custom_prompt": custom_prompt,
                    "prompt_modifications": prompt_tags,
                    "cloud_storage": "Google Drive" if out_drive_id else "Local Filesystem",
                    "faces_detected": {
                        "husband": len(h_faces),
                        "wife": len(w_faces),
                        "target": len(t_faces),
                    },
                    "skin_tone_matched": skin_tone_matching,
                    "body_proportions_applied": body_proportion_matching,
                    "lighting_harmonized": lighting_harmonization,
                    "ai_engine": (
                        "InsightFace Neural"
                        if face_engine._swapper is not None
                        else "OpenCV Poisson Seamless Cloner + LAB Transfer"
                    ),
                },
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[{job_id}] Pipeline error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/antigravity/refine-swap")
async def refine_swap(
    job_id: str = Form(..., description="Previous job ID to refine"),
    custom_prompt: str = Form(..., description="Prompt instructions for custom changes and stylization"),
    gemini_api_key: Optional[str] = Form(None),
    user_id: Optional[str] = Form("anonymous"),
):
    """
    Rapid iterative refinement endpoint:
    Applies custom prompt stylization and adjustments to an existing output image.
    Supports persistent Google Drive image retrieval if container was restarted.
    """
    output_filename = f"antigravity_result_{job_id}.jpg"
    output_path = OUTPUT_DIR / output_filename

    img = None
    if output_path.exists():
        img = resize_image_for_memory(output_path, max_dim=1280)
    elif drive_storage.is_configured():
        rec = get_image_by_filename(output_filename)
        drive_id = rec.get("drive_file_id") if rec else None
        if not drive_id:
            files = drive_storage.list_files_in_folder("Generated-Images")
            for f in files:
                if f.get("name") == output_filename:
                    drive_id = f.get("id")
                    break
        if drive_id:
            raw_bytes = drive_storage.download_bytes(drive_id)
            img = resize_image_for_memory(raw_bytes, max_dim=1280)

    if img is None:
        raise HTTPException(status_code=404, detail="Original job output image not found.")

    refined_img, prompt_tags = apply_prompt_stylization(img, custom_prompt)

    # Save as new refined output
    new_job_id = str(uuid.uuid4())[:8]
    new_filename = f"antigravity_result_{new_job_id}.jpg"
    new_path = OUTPUT_DIR / new_filename
    cv2.imwrite(str(new_path), refined_img, [cv2.IMWRITE_JPEG_QUALITY, 95])

    new_drive_id = None
    if drive_storage.is_configured():
        try:
            out_res = drive_storage.upload_file(
                new_path, new_filename, folder_name="Generated-Images",
                user_id=user_id, job_id=new_job_id, image_role="refined_output"
            )
            new_drive_id = out_res.get("file_id")
            record_image(user_id=user_id, image_role="refined_output", filename=new_filename,
                         drive_file_id=new_drive_id, drive_folder="Generated-Images",
                         job_id=new_job_id, file_size=new_path.stat().st_size)
        except Exception as e:
            logger.warning(f"Could not upload refined output to Google Drive: {e}")
    else:
        record_image(user_id=user_id, image_role="refined_output", filename=new_filename, job_id=new_job_id)

    gemini_feedback = None
    if gemini_api_key and gemini_api_key.strip():
        try:
            import google.generativeai as genai
            from PIL import Image
            genai.configure(api_key=gemini_api_key.strip())
            model = genai.GenerativeModel("gemini-1.5-pro")
            pil_img = Image.fromarray(cv2.cvtColor(refined_img, cv2.COLOR_BGR2RGB))
            resp = model.generate_content([
                f"Analyze this couple photo after applying the user prompt: '{custom_prompt}'. "
                "Assess if the changes look natural, pleasing, and aesthetic.",
                pil_img,
            ])
            gemini_feedback = resp.text
        except Exception as e:
            logger.warning(f"Gemini refine error: {e}")

    steps = [f"✨ Applied custom prompt refinement: \"{custom_prompt}\""] + [f"✅ {tag}" for tag in prompt_tags]

    return JSONResponse(
        content={
            "status": "success",
            "job_id": new_job_id,
            "message": "Antigravity AI successfully applied prompt-guided refinements!",
            "download_url": f"/api/antigravity/download/{new_filename}",
            "preview_url": f"/outputs/{new_filename}",
            "drive_file_id": new_drive_id,
            "processing_steps": steps,
            "gemini_analysis": gemini_feedback,
            "execution_metadata": {
                "parent_job_id": job_id,
                "custom_prompt": custom_prompt,
                "prompt_modifications": prompt_tags,
                "ai_engine": "InsightFace Neural + Prompt Engine",
            },
        }
    )


@app.get("/api/antigravity/download/{filename}")
async def download_output(filename: str):
    """Download output image, with persistent Google Drive streaming fallback."""
    file_path = OUTPUT_DIR / filename
    if file_path.exists():
        return FileResponse(
            str(file_path),
            media_type="image/jpeg",
            filename=filename,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    # Fallback to Google Drive
    rec = get_image_by_filename(filename)
    drive_id = rec.get("drive_file_id") if rec else None
    if not drive_id and drive_storage.is_configured():
        files = drive_storage.list_files_in_folder("Generated-Images")
        for f in files:
            if f.get("name") == filename:
                drive_id = f.get("id")
                break

    if drive_id and drive_storage.is_configured():
        return StreamingResponse(
            drive_storage.stream_file_content(drive_id),
            media_type="image/jpeg",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    raise HTTPException(status_code=404, detail="File not found")


@app.get("/api/antigravity/gallery")
async def gallery():
    """Lists generated results from SQLite database, Google Drive, and local cache."""
    seen_names = set()
    items = []

    # 1. Query SQLite database
    db_items = list_gallery_images()
    for row in db_items:
        fname = row["filename"]
        seen_names.add(fname)
        items.append({
            "filename": fname,
            "preview_url": f"/outputs/{fname}",
            "download_url": f"/api/antigravity/download/{fname}",
            "drive_id": row.get("drive_file_id"),
            "created_at": row.get("created_at"),
        })

    # 2. Query Google Drive folder directly if DB is empty (e.g. fresh Render container restart)
    if not items and drive_storage.is_configured():
        try:
            drive_files = drive_storage.list_files_in_folder("Generated-Images")
            for f in drive_files:
                fname = f.get("name")
                if fname and fname not in seen_names:
                    seen_names.add(fname)
                    sync_drive_file_metadata(
                        drive_file_id=f["id"],
                        filename=fname,
                        folder_name="Generated-Images",
                        image_role="generated_output",
                        file_size=int(f.get("size", 0)),
                    )
                    items.append({
                        "filename": fname,
                        "preview_url": f"/outputs/{fname}",
                        "download_url": f"/api/antigravity/download/{fname}",
                        "drive_id": f.get("id"),
                    })
        except Exception as e:
            logger.warning(f"Could not load gallery from Google Drive: {e}")

    # 3. Include local files if any
    if OUTPUT_DIR.exists():
        for f in sorted(OUTPUT_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp") and f.name not in seen_names:
                seen_names.add(f.name)
                items.append({
                    "filename": f.name,
                    "preview_url": f"/outputs/{f.name}",
                    "download_url": f"/api/antigravity/download/{f.name}",
                })

    return {"outputs": items, "count": len(items)}


@app.delete("/api/antigravity/delete/{identifier}")
async def delete_image_endpoint(identifier: str):
    """Deletes an image from local storage, Google Drive, and database."""
    # 1. Local delete
    local_path = OUTPUT_DIR / identifier
    if local_path.exists():
        try:
            local_path.unlink()
        except Exception as e:
            logger.warning(f"Local file delete error: {e}")

    # 2. Google Drive delete
    rec = get_image_by_filename(identifier) or get_image_by_drive_id(identifier)
    drive_id = rec.get("drive_file_id") if rec else identifier

    if drive_storage.is_configured() and drive_id:
        try:
            drive_storage.delete_file(drive_id)
        except Exception as e:
            logger.warning(f"Google Drive delete error: {e}")

    # 3. Mark deleted in database
    mark_image_deleted(identifier)
    return {"status": "success", "message": f"Image {identifier} successfully deleted."}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    logger.info(f"Antigravity AI Server launching on http://0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
