const BASE = "/api";

export async function uploadFile(file, onProgress) {
  const formData = new FormData();
  formData.append("file", file);

  const xhr = new XMLHttpRequest();
  return new Promise((resolve, reject) => {
    xhr.upload.addEventListener("progress", (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    });
    xhr.addEventListener("load", () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText));
      } else {
        reject(new Error(xhr.responseText || "Upload failed"));
      }
    });
    xhr.addEventListener("error", () => reject(new Error("Network error")));
    xhr.open("POST", `${BASE}/upload`);
    xhr.send(formData);
  });
}

export async function getResults(jobId) {
  const res = await fetch(`${BASE}/results/${jobId}`);
  if (!res.ok) {
    let message = "Failed to fetch results";
    try {
      const payload = await res.json();
      message = payload?.detail || message;
    } catch {
      // keep default error message
    }
    throw new Error(message);
  }
  return res.json();
}

export async function exportImages(jobId, selected) {
  const res = await fetch(`${BASE}/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_id: jobId, selected_ids: selected }),
  });
  if (!res.ok) {
    let message = "Export failed";
    try {
      const payload = await res.json();
      message = payload?.detail || message;
    } catch {
      // keep default error message
    }
    throw new Error(message);
  }

  const blob = await res.blob();
  const contentDisp = res.headers.get("Content-Disposition") || "";
  const match = contentDisp.match(/filename="?(.+?)"?$/);
  const filename = match ? match[1] : "export.png";

  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
