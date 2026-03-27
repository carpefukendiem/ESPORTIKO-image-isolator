# ESPORTIKO Image Isolator

Upload a sheet of cartoon/clip-art images, automatically detect and isolate each one, then export print-ready PNGs optimized for the **Roland TrueVIS SG2-540** wide-format printer.

## Quick Start

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Optional high-quality background removal (`rembg` + `u2net`):

```bash
pip install -r requirements-rembg.txt
```

Optional OpenCV contour pipeline (faster/more robust on dense sheets):

```bash
pip install -r requirements-opencv.txt
```

> **Note:** PDF support requires `poppler`. Install via `brew install poppler` (macOS) or `apt-get install poppler-utils` (Linux).

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** in your browser.

## API

- `POST /api/upload` -> multipart `file`, returns `{ job_id, count }`
- `GET /api/results/{job_id}` -> returns isolated image list for selection UI
- `POST /api/export` -> body `{ job_id, selected_ids: [{ id, name }] }`, returns PNG or ZIP

## How It Works

1. **Upload** a JPG, PNG, PDF, or other image file containing multiple images on one sheet
2. The backend uses OpenCV contour detection and contour merging to find each distinct image element
3. Each element is cropped with padding and background isolation is applied (uses `rembg` automatically when installed)
4. The frontend displays all detected images as selectable thumbnails
5. Name your images, select the ones you want, and export as print-optimized PNGs (300 DPI, sRGB, RGBA)

## Docker

```bash
docker compose up --build
```

Backend: `http://localhost:8000`  
Frontend: `http://localhost:5173`
