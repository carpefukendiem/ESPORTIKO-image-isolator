"""FastAPI application for ESPORTIKO Image Isolator."""

import shutil
from pathlib import Path
from typing import List

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

from isolator import process_file, TEMP_DIR
from exporter import export_single, export_multiple, _safe_name

app = FastAPI(title="ESPORTIKO Image Isolator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf", ".webp", ".tiff", ".tif"}

# In-memory store for job results (sufficient for local single-user use)
jobs: dict = {}


class ImageSelection(BaseModel):
    id: str
    name: str


class ExportRequest(BaseModel):
    job_id: str
    selected_ids: List[ImageSelection] = Field(default_factory=list)
    selected: List[ImageSelection] = Field(default_factory=list)


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload a file for image isolation processing."""
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type: {ext}")

    contents = await file.read()
    if len(contents) == 0:
        raise HTTPException(400, "Empty file")

    try:
        result = process_file(contents, file.filename or "upload.png")
    except Exception as e:
        raise HTTPException(500, f"Processing failed: {str(e)}")

    jobs[result["job_id"]] = result
    return {"job_id": result["job_id"], "count": len(result["images"])}


@app.get("/api/results/{job_id}")
async def get_results(job_id: str):
    """Get isolation results for a job."""
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    data = jobs[job_id]
    return {"job_id": job_id, "images": data["images"]}


@app.post("/api/export")
async def export_images(req: ExportRequest):
    """Export selected images as optimized PNGs."""
    if req.job_id not in jobs:
        raise HTTPException(404, "Job not found")

    requested = req.selected_ids or req.selected
    selections = [{"id": s.id, "name": s.name} for s in requested]
    if not selections:
        raise HTTPException(400, "No images selected")

    try:
        if len(selections) == 1:
            png_bytes = export_single(req.job_id, selections[0]["id"], selections[0]["name"])
            return Response(
                content=png_bytes,
                media_type="image/png",
                headers={
                    "Content-Disposition": f'attachment; filename="{_safe_name(selections[0]["name"])}.png"'
                },
            )
        else:
            zip_bytes = export_multiple(req.job_id, selections)
            return Response(
                content=zip_bytes,
                media_type="application/zip",
                headers={
                    "Content-Disposition": 'attachment; filename="esportiko_export.zip"'
                },
            )
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@app.delete("/api/jobs/{job_id}")
async def delete_job(job_id: str):
    """Clean up a job's temp files."""
    job_dir = TEMP_DIR / job_id
    if job_dir.exists():
        shutil.rmtree(job_dir)
    jobs.pop(job_id, None)
    return {"status": "ok"}
