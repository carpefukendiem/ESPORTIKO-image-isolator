import { useState } from "react";
import UploadZone from "./components/UploadZone";
import ImageGrid from "./components/ImageGrid";
import ExportBar from "./components/ExportBar";
import { uploadFile, getResults, exportImages } from "./api";

export default function App() {
  const [status, setStatus] = useState("idle"); // idle | uploading | processing | done | error
  const [progress, setProgress] = useState(0);
  const [jobId, setJobId] = useState(null);
  const [images, setImages] = useState([]);
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState(null);

  const handleUpload = async (file) => {
    setStatus("uploading");
    setProgress(0);
    setError(null);
    setImages([]);
    setSelectedIds(new Set());
    setJobId(null);

    try {
      const upload = await uploadFile(file, (p) => setProgress(p));
      setStatus("processing");
      setJobId(upload.job_id);

      const result = await getResults(upload.job_id);
      setImages(result.images);
      setSelectedIds(new Set(result.images.map((i) => i.id)));
      setStatus("done");
    } catch (err) {
      setError(err.message || "Upload failed");
      setStatus("error");
    }
  };

  const toggleSelect = (id) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleNameChange = (id, name) => {
    setImages((prev) =>
      prev.map((img) => (img.id === id ? { ...img, name } : img))
    );
  };

  const handleExport = async () => {
    setExporting(true);
    try {
      const selected = images
        .filter((img) => selectedIds.has(img.id))
        .map((img) => ({ id: img.id, name: img.name }));
      await exportImages(jobId, selected);
    } catch (err) {
      setError(err.message || "Export failed");
    }
    setExporting(false);
  };

  const handleReset = () => {
    setStatus("idle");
    setImages([]);
    setSelectedIds(new Set());
    setJobId(null);
    setError(null);
  };

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 pb-24">
      <header className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight">
          ESPORTIKO Image Isolator
        </h1>
        <p className="text-gray-400 mt-1">
          Upload a sheet of images, isolate each one, and export print-ready
          PNGs for the Roland TrueVIS SG2-540.
        </p>
      </header>

      {status === "idle" && <UploadZone onUpload={handleUpload} />}

      {(status === "uploading" || status === "processing") && (
        <div className="text-center py-16">
          <div className="inline-block w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mb-4" />
          <p className="text-gray-300">
            {status === "uploading"
              ? `Uploading... ${progress}%`
              : "Detecting and isolating images..."}
          </p>
        </div>
      )}

      {error && (
        <div className="bg-red-900/40 border border-red-700 rounded-lg p-4 mb-6">
          <p className="text-red-300">{error}</p>
        </div>
      )}

      {status === "done" && images.length === 0 && (
        <div className="text-center py-16">
          <p className="text-gray-400 mb-4">
            No images were detected in the uploaded file.
          </p>
          <button
            onClick={handleReset}
            className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors"
          >
            Try Another File
          </button>
        </div>
      )}

      {status === "done" && images.length > 0 && (
        <>
          <div className="flex justify-end mb-4">
            <button
              onClick={handleReset}
              className="px-4 py-2 text-sm bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors"
            >
              Upload New File
            </button>
          </div>
          <ImageGrid
            images={images}
            selectedIds={selectedIds}
            onToggle={toggleSelect}
            onNameChange={handleNameChange}
            onSelectAll={() =>
              setSelectedIds(new Set(images.map((i) => i.id)))
            }
            onDeselectAll={() => setSelectedIds(new Set())}
          />
        </>
      )}

      <ExportBar
        selectedCount={selectedIds.size}
        onExport={handleExport}
        exporting={exporting}
        disabled={!jobId}
      />
    </div>
  );
}
