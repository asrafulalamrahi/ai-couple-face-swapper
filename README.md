# AI Couple Face Swapper Studio

An autonomous, production-grade couple face swapping and body proportion matching engine powered by InsightFace neural embeddings, OpenCV Poisson seamless cloning, Reinhard skin tone harmonization, and natural language prompt refinement.

---

## 🌟 Key Features

- **Dual-Engine Face Swap Pipeline**:
  - **Neural Mode**: InsightFace `buffalo_l` detection with `inswapper_128` deep neural face transfer.
  - **Fallback Mode**: OpenCV Haar Cascade detector paired with Poisson Seamless Cloning (`cv2.seamlessClone`).
- **Autonomous Couple Face Mapping**: Explicitly maps source husband and wife portraits to respective subjects in the target couple photograph.
- **LAB Skin Tone Harmonization**: Reinhard color transfer in the CIELAB color space matching mean and standard deviation between source and target skin textures.
- **Lighting & Contrast Normalization**: HSV V-channel specification ensures seamless blend with ambient scene illumination.
- **Natural Language Refinements**: Built-in prompt engine for post-processing adjustments (e.g. golden hour warmth, cinematic contrast, soft skin glow, aesthetic color grading).
- **Quality Assessment**: Multimodal vision analysis integration (Gemini Vision) for real-time naturalness assessment.
- **Built-in Web Studio**: Responsive dark-mode studio interface served directly by the backend at `http://localhost:8000/`.

---

## 📁 Project Structure

```
├── backend/
│   ├── antigravity_master_backend.py  # FastAPI server & dual swap engine
│   ├── requirements.txt               # Backend Python dependencies
│   ├── static/                        # Self-contained Web Studio frontend
│   │   └── index.html
│   └── antigravity_storage/
│       ├── models/                    # InsightFace models (buffalo_l, inswapper_128.onnx)
│       ├── uploads/                   # Runtime upload staging
│       └── outputs/                   # Processed outputs & downloads
├── frontend/                          # Vite + React + TypeScript frontend
│   ├── src/
│   │   ├── components/
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   └── vite.config.ts
├── .gitignore
└── README.md
```

---

## 🚀 Getting Started

### Prerequisites

- **Python**: 3.10 to 3.13
- **Node.js**: v18+ (optional, for frontend Vite dev server)
- **Model Weights**: `inswapper_128.onnx` and InsightFace `buffalo_l` placed in `backend/antigravity_storage/models/`.

### 1. Backend Setup & Launch

1. Install Python dependencies:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. Download model weights:
   - Place `inswapper_128.onnx` into `backend/antigravity_storage/models/`
   - InsightFace will automatically download `buffalo_l` to the models directory on first run if not present.

3. Start the FastAPI server:
   ```bash
   python antigravity_master_backend.py
   ```
   The studio will be available at [http://localhost:8000](http://localhost:8000).
   Interactive API docs (Swagger UI) are at [http://localhost:8000/docs](http://localhost:8000/docs).

### 2. Frontend Development (Optional)

If you wish to run the React + Vite development server:
```bash
cd frontend
npm install
npm run dev
```
The Vite dev server proxies API calls (`/api`, `/outputs`) to the backend running on port 8000.

### 3. Deploying to Render with Persistent Google Drive Storage

This repository includes native Render configuration files (`render.yaml` and `.python-version`):

- **Service Type**: Web Service
- **Runtime**: Python 3 (Python 3.11.9)
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `python backend/antigravity_master_backend.py`
- **Environment Variables**:
  - `PYTHON_VERSION`: `3.11.9`
  - `PORT`: Automatically assigned by Render
  - `GOOGLE_DRIVE_CLIENT_ID`: Your Google OAuth 2.0 Web Client ID
  - `GOOGLE_DRIVE_CLIENT_SECRET`: Your Google OAuth 2.0 Client Secret
  - `GOOGLE_DRIVE_REFRESH_TOKEN`: Your OAuth 2.0 Refresh Token with Drive access
  - `GOOGLE_DRIVE_FOLDER_ID`: The folder ID of your root Google Drive folder (e.g., `AI-Couple-Face-Swapper`)
  - `GEMINI_API_KEY`: *(Optional)* For Gemini Pro Vision multimodal quality assessment

---

## ☁️ Google Drive Architecture

When configured, images bypass ephemeral container disk storage and persist in Google Drive with the following structure:
```text
AI-Couple-Face-Swapper/
  ├── Original-Uploads/    # Source portraits uploaded by users
  ├── Generated-Images/    # High-resolution AI-swapped portraits
  ├── User-Images/         # User profile portraits & assets
  └── Backups/             # Archive & fallback storage
```
- **Privacy First**: Files are never set to public or world-readable; access is authenticated and proxied securely via backend streaming endpoints (`/outputs/{filename}` and `/api/antigravity/download/{filename}`).
- **Crash/Restart Resilient**: Cold container restarts query Google Drive metadata (`appProperties`) to immediately rebuild the SQLite gallery and history index without data loss.

---

## 🔌 API Endpoints

- `GET /api/health` — Checks engine readiness, active backend mode, and Google Drive connection status.
- `POST /api/antigravity/execute-couple-swap` — Executes couple face swap, synchronizes images directly to Google Drive, and records metadata.
- `POST /api/antigravity/refine-swap` — Applies prompt-guided enhancements (retrieves previous output from Google Drive if necessary).
- `GET /api/antigravity/gallery` — Returns history of generated results from SQLite and Google Drive.
- `GET /outputs/{filename}` — Streams image directly from local cache or Google Drive.
- `GET /api/antigravity/download/{filename}` — Secure authenticated download of high-resolution image.
- `DELETE /api/antigravity/delete/{identifier}` — Deletes an image from local disk, Google Drive, and database.

---

## 🛡️ License

MIT License

