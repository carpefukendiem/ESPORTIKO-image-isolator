"""Image segmentation and isolation engine.

Detects individual image elements from an uploaded file (which may contain
multiple cartoon/clip-art images on a single sheet) and isolates each one
with background removal.
"""

import base64
import io
import uuid
from collections import deque
from pathlib import Path
from typing import List, Dict, Any

import numpy as np
from PIL import Image, ImageFilter
try:
    import cv2

    CV2_AVAILABLE = True
except Exception:
    CV2_AVAILABLE = False
try:
    from rembg import remove, new_session

    REMBG_SESSION = new_session("u2net")
    REMBG_AVAILABLE = True
except Exception:
    REMBG_SESSION = None
    REMBG_AVAILABLE = False

TEMP_DIR = Path(__file__).parent / "temp"
TEMP_DIR.mkdir(exist_ok=True)

# Minimum contour size to keep (filters noise)
MIN_WIDTH = 50
MIN_HEIGHT = 50
# Merge contours within this pixel distance
MERGE_DISTANCE = 20
# Transparent padding around each isolated element
PADDING = 10
BG_COLOR_DISTANCE_THRESHOLD = 28
BG_FLOOD_THRESHOLD = 72


def _load_images_from_file(file_bytes: bytes, filename: str) -> List[Image.Image]:
    """Load one or more PIL Images from the uploaded file bytes."""
    ext = Path(filename).suffix.lower()

    if ext == ".pdf":
        try:
            from pdf2image import convert_from_bytes
            pages = convert_from_bytes(file_bytes, dpi=300)
            return pages
        except Exception as e:
            raise ValueError(
                f"Failed to process PDF. Ensure poppler is installed. Details: {e}"
            )
    else:
        img = Image.open(io.BytesIO(file_bytes))
        return [img]


def _merge_boxes(boxes: List[List[int]], distance: int) -> List[List[int]]:
    """Merge bounding boxes that overlap or are within `distance` px."""
    if not boxes:
        return boxes

    merged = True
    while merged:
        merged = False
        new_boxes = []
        used = set()
        for i in range(len(boxes)):
            if i in used:
                continue
            x1, y1, w1, h1 = boxes[i]
            r1, b1 = x1 + w1, y1 + h1
            for j in range(i + 1, len(boxes)):
                if j in used:
                    continue
                x2, y2, w2, h2 = boxes[j]
                r2, b2 = x2 + w2, y2 + h2
                # Check if boxes overlap or are within merge distance
                if not (r1 + distance < x2 or r2 + distance < x1 or
                        b1 + distance < y2 or b2 + distance < y1):
                    # Merge
                    nx = min(x1, x2)
                    ny = min(y1, y2)
                    nr = max(r1, r2)
                    nb = max(b1, b2)
                    boxes[i] = [nx, ny, nr - nx, nb - ny]
                    x1, y1, w1, h1 = boxes[i]
                    r1, b1 = x1 + w1, y1 + h1
                    used.add(j)
                    merged = True
            new_boxes.append(boxes[i])
        boxes = new_boxes

    return boxes


def _detect_regions(pil_img: Image.Image) -> List[List[int]]:
    """Detect bounding boxes of distinct image elements via contour analysis."""
    img_rgba = pil_img.convert("RGBA")
    img_np = np.array(img_rgba)

    # Convert to grayscale for thresholding
    gray = np.dot(img_np[:, :, :3], [0.299, 0.587, 0.114]).astype(np.uint8)
    alpha = img_np[:, :, 3] if img_np.shape[2] == 4 else np.full(gray.shape, 255, dtype=np.uint8)
    bg_colors = _estimate_background_colors(img_np[:, :, :3])
    bg_connected = _background_connected_mask(img_np[:, :, :3], bg_colors, BG_FLOOD_THRESHOLD)
    # Pixels not connected to border background are considered foreground.
    content_mask = ((~bg_connected) & (alpha > 128)).astype(np.uint8)

    if CV2_AVAILABLE:
        # Flood-fill border background, then invert to get foreground objects.
        rgb = img_np[:, :, :3].copy()
        h, w = gray.shape
        ff_mask = np.zeros((h + 2, w + 2), dtype=np.uint8)
        seed_step = max(8, min(h, w) // 30)

        seeds = []
        for x in range(0, w, seed_step):
            seeds.append((x, 0))
            seeds.append((x, h - 1))
        for y in range(0, h, seed_step):
            seeds.append((0, y))
            seeds.append((w - 1, y))

        for sx, sy in seeds:
            if gray[sy, sx] < 150:
                continue
            cv2.floodFill(
                rgb,
                ff_mask,
                seedPoint=(sx, sy),
                newVal=(0, 0, 0),
                loDiff=(28, 28, 28),
                upDiff=(28, 28, 28),
                flags=cv2.FLOODFILL_FIXED_RANGE | 4,
            )

        bg_mask = (ff_mask[1:-1, 1:-1] > 0).astype(np.uint8) * 255
        cv_mask = cv2.bitwise_not(bg_mask)
        cv_mask = cv2.bitwise_and(cv_mask, (alpha > 128).astype(np.uint8) * 255)

        # Opening breaks thin noise links; closing restores compact shapes.
        k_open = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        k_close = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        cv_mask = cv2.morphologyEx(cv_mask, cv2.MORPH_OPEN, k_open, iterations=1)
        cv_mask = cv2.morphologyEx(cv_mask, cv2.MORPH_CLOSE, k_close, iterations=1)

        contours, _ = cv2.findContours(cv_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        split_mask = (cv_mask > 0).astype(np.uint8)

        boxes = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if w >= MIN_WIDTH and h >= MIN_HEIGHT:
                boxes.append([x, y, w, h])
    else:
        # Break tiny noise bridges so separate stickers don't collapse into one component.
        mask_img = Image.fromarray((content_mask * 255).astype(np.uint8))
        mask_img = mask_img.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.MaxFilter(5))
        content_mask = (np.array(mask_img) > 0).astype(np.uint8)
        boxes = _connected_components_boxes(content_mask)
        split_mask = content_mask

    # Merge nearby/overlapping boxes
    boxes = _merge_boxes(boxes, MERGE_DISTANCE)
    boxes = _split_boxes_by_whitespace(split_mask, boxes)

    return boxes


def _estimate_background_colors(rgb: np.ndarray, bins: int = 16, top_k: int = 3) -> List[np.ndarray]:
    """Estimate dominant background colors from image borders."""
    h, w, _ = rgb.shape
    border = np.vstack(
        [
            rgb[0, :, :],
            rgb[h - 1, :, :],
            rgb[:, 0, :],
            rgb[:, w - 1, :],
        ]
    )
    q = (border // bins).astype(np.int16)
    keys = (q[:, 0] << 8) + (q[:, 1] << 4) + q[:, 2]
    uniq, counts = np.unique(keys, return_counts=True)
    order = np.argsort(counts)[::-1][:top_k]
    colors: List[np.ndarray] = []
    for idx in order:
        key = uniq[idx]
        r = (key >> 8) & 0xF
        g = (key >> 4) & 0xF
        b = key & 0xF
        center = np.array(
            [
                int(r * bins + bins / 2),
                int(g * bins + bins / 2),
                int(b * bins + bins / 2),
            ],
            dtype=np.int16,
        )
        colors.append(center)
    if not colors:
        colors.append(np.array([245, 245, 245], dtype=np.int16))
    return colors


def _background_distance_mask(rgb: np.ndarray, bg_colors: List[np.ndarray]) -> np.ndarray:
    """Return True where pixels are far enough from all estimated bg colors."""
    px = rgb.astype(np.int16)
    # Start with very high minimum distance; then reduce across bg colors.
    min_dist = np.full(px.shape[:2], 10000, dtype=np.int32)
    for bg in bg_colors:
        diff = px - bg
        dist = (diff[:, :, 0] * diff[:, :, 0]) + (diff[:, :, 1] * diff[:, :, 1]) + (
            diff[:, :, 2] * diff[:, :, 2]
        )
        min_dist = np.minimum(min_dist, dist)
    return min_dist > (BG_COLOR_DISTANCE_THRESHOLD * BG_COLOR_DISTANCE_THRESHOLD)


def _background_connected_mask(rgb: np.ndarray, bg_colors: List[np.ndarray], threshold: int) -> np.ndarray:
    """Flood-fill border-connected background candidates."""
    px = rgb.astype(np.int16)
    h, w, _ = px.shape
    thr2 = threshold * threshold

    candidate = np.zeros((h, w), dtype=bool)
    for bg in bg_colors:
        diff = px - bg
        dist = (diff[:, :, 0] * diff[:, :, 0]) + (diff[:, :, 1] * diff[:, :, 1]) + (
            diff[:, :, 2] * diff[:, :, 2]
        )
        candidate |= dist <= thr2

    visited = np.zeros((h, w), dtype=bool)
    q = deque()

    for x in range(w):
        if candidate[0, x]:
            q.append((x, 0))
            visited[0, x] = True
        if candidate[h - 1, x] and not visited[h - 1, x]:
            q.append((x, h - 1))
            visited[h - 1, x] = True
    for y in range(h):
        if candidate[y, 0] and not visited[y, 0]:
            q.append((0, y))
            visited[y, 0] = True
        if candidate[y, w - 1] and not visited[y, w - 1]:
            q.append((w - 1, y))
            visited[y, w - 1] = True

    while q:
        cx, cy = q.popleft()
        for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
            if 0 <= nx < w and 0 <= ny < h and candidate[ny, nx] and not visited[ny, nx]:
                visited[ny, nx] = True
                q.append((nx, ny))

    return visited


def _connected_components_boxes(mask: np.ndarray) -> List[List[int]]:
    """Fallback region detection when OpenCV isn't installed."""
    h, w = mask.shape
    visited = np.zeros_like(mask, dtype=np.uint8)
    boxes: List[List[int]] = []

    for y in range(h):
        for x in range(w):
            if mask[y, x] == 0 or visited[y, x]:
                continue

            q = deque([(x, y)])
            visited[y, x] = 1
            min_x = max_x = x
            min_y = max_y = y

            while q:
                cx, cy = q.popleft()
                if cx < min_x:
                    min_x = cx
                if cx > max_x:
                    max_x = cx
                if cy < min_y:
                    min_y = cy
                if cy > max_y:
                    max_y = cy

                for nx, ny in (
                    (cx - 1, cy),
                    (cx + 1, cy),
                    (cx, cy - 1),
                    (cx, cy + 1),
                    (cx - 1, cy - 1),
                    (cx + 1, cy - 1),
                    (cx - 1, cy + 1),
                    (cx + 1, cy + 1),
                ):
                    if 0 <= nx < w and 0 <= ny < h and mask[ny, nx] and not visited[ny, nx]:
                        visited[ny, nx] = 1
                        q.append((nx, ny))

            bw = max_x - min_x + 1
            bh = max_y - min_y + 1
            if bw >= MIN_WIDTH and bh >= MIN_HEIGHT:
                boxes.append([min_x, min_y, bw, bh])

    return boxes


def _split_boxes_by_whitespace(mask: np.ndarray, boxes: List[List[int]], depth: int = 0) -> List[List[int]]:
    """Split large connected boxes using empty row/column valleys."""
    if depth >= 4:
        return boxes

    out: List[List[int]] = []
    changed = False
    for box in boxes:
        children = _split_single_box(mask, box)
        if len(children) > 1:
            changed = True
            out.extend(children)
        else:
            out.append(box)

    if changed:
        return _split_boxes_by_whitespace(mask, out, depth + 1)
    return out


def _split_single_box(mask: np.ndarray, box: List[int]) -> List[List[int]]:
    x, y, w, h = box
    if w < 2 * MIN_WIDTH or h < 2 * MIN_HEIGHT:
        return [box]

    sub = mask[y : y + h, x : x + w]
    row_fill = sub.mean(axis=1)
    col_fill = sub.mean(axis=0)

    row_cut = _best_empty_run(row_fill, min_run=8, min_margin=12)
    col_cut = _best_empty_run(col_fill, min_run=8, min_margin=12)

    if row_cut is None and col_cut is None:
        return [box]

    if row_cut is not None and (col_cut is None or row_cut[1] >= col_cut[1]):
        cut_y = y + row_cut[0]
        top_h = cut_y - y
        bottom_h = (y + h) - cut_y
        if top_h >= MIN_HEIGHT and bottom_h >= MIN_HEIGHT:
            return [[x, y, w, top_h], [x, cut_y, w, bottom_h]]
        return [box]

    cut_x = x + col_cut[0]
    left_w = cut_x - x
    right_w = (x + w) - cut_x
    if left_w >= MIN_WIDTH and right_w >= MIN_WIDTH:
        return [[x, y, left_w, h], [cut_x, y, right_w, h]]
    return [box]


def _best_empty_run(fill: np.ndarray, min_run: int, min_margin: int):
    empty = fill < 0.015
    n = len(empty)
    best = None
    i = 0
    while i < n:
        if not empty[i]:
            i += 1
            continue
        j = i
        while j < n and empty[j]:
            j += 1
        run_len = j - i
        center = (i + j) // 2
        if run_len >= min_run and center >= min_margin and center <= (n - min_margin):
            if best is None or run_len > best[1]:
                best = (center, run_len)
        i = j
    return best


def _crop_and_remove_bg(pil_img: Image.Image, box: List[int]) -> Image.Image:
    """Crop region from image, remove background, add padding."""
    x, y, w, h = box
    img_rgba = pil_img.convert("RGBA")
    img_w, img_h = img_rgba.size

    # Crop with a small extra margin for better rembg results
    margin = 5
    left = max(0, x - margin)
    top = max(0, y - margin)
    right = min(img_w, x + w + margin)
    bottom = min(img_h, y + h + margin)
    crop = img_rgba.crop((left, top, right, bottom))

    if REMBG_AVAILABLE:
        # Remove background with rembg/u2net.
        crop_bytes = io.BytesIO()
        crop.save(crop_bytes, format="PNG")
        crop_bytes.seek(0)
        try:
            result_bytes = remove(crop_bytes.read(), session=REMBG_SESSION)
            result = Image.open(io.BytesIO(result_bytes)).convert("RGBA")
        except Exception:
            # Graceful fallback if rembg model/runtime has issues.
            result = crop
    else:
        result = crop

    # Trim fully transparent edges
    bbox = result.getbbox()
    if bbox:
        result = result.crop(bbox)

    # Add padding
    padded = Image.new("RGBA",
                       (result.width + PADDING * 2, result.height + PADDING * 2),
                       (0, 0, 0, 0))
    padded.paste(result, (PADDING, PADDING))

    return padded


def _to_thumbnail_b64(img: Image.Image, max_size: int = 300) -> str:
    """Create a base64-encoded thumbnail for the API response."""
    thumb = img.copy()
    thumb.thumbnail((max_size, max_size), Image.LANCZOS)
    buf = io.BytesIO()
    thumb.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def process_file(file_bytes: bytes, filename: str) -> Dict[str, Any]:
    """Main entry point: process an uploaded file and return isolated images.

    Returns a dict with job_id and a list of detected image metadata.
    The full-resolution isolated images are saved to disk under temp/<job_id>/.
    """
    job_id = str(uuid.uuid4())
    job_dir = TEMP_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    pages = _load_images_from_file(file_bytes, filename)

    results: List[Dict[str, Any]] = []
    image_index = 0

    for page in pages:
        boxes = _detect_regions(page)

        for box in boxes:
            image_index += 1
            img_id = str(uuid.uuid4())
            isolated = _crop_and_remove_bg(page, box)

            # Save full-res to disk
            out_path = job_dir / f"{img_id}.png"
            isolated.save(str(out_path), "PNG")

            results.append({
                "id": img_id,
                "name": f"image_{image_index}",
                "thumbnail": _to_thumbnail_b64(isolated),
                "width": isolated.width,
                "height": isolated.height,
                "box": box,
            })

    return {"job_id": job_id, "images": results}
