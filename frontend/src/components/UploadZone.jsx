import { useCallback, useState } from "react";

const ACCEPT = ".jpg,.jpeg,.png,.pdf,.webp,.tiff,.tif";

export default function UploadZone({ onUpload, disabled }) {
  const [dragging, setDragging] = useState(false);

  const handleFile = useCallback(
    (file) => {
      if (file && onUpload) onUpload(file);
    },
    [onUpload]
  );

  const onDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    handleFile(file);
  };

  const onDragOver = (e) => {
    e.preventDefault();
    setDragging(true);
  };

  const onDragLeave = () => setDragging(false);

  const onChange = (e) => {
    const file = e.target.files[0];
    handleFile(file);
    e.target.value = "";
  };

  return (
    <div
      onDrop={onDrop}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      className={`border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors ${
        dragging
          ? "border-blue-400 bg-blue-400/10"
          : "border-gray-600 hover:border-gray-400"
      } ${disabled ? "opacity-50 pointer-events-none" : ""}`}
      onClick={() => document.getElementById("file-input").click()}
    >
      <input
        id="file-input"
        type="file"
        accept={ACCEPT}
        onChange={onChange}
        className="hidden"
      />
      <svg
        className="mx-auto mb-4 w-12 h-12 text-gray-400"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={1.5}
          d="M12 16V4m0 0L8 8m4-4l4 4M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2"
        />
      </svg>
      <p className="text-lg text-gray-300 mb-1">
        Drop an image or PDF here, or click to browse
      </p>
      <p className="text-sm text-gray-500">
        JPG, PNG, PDF, WebP, TIFF supported
      </p>
    </div>
  );
}
