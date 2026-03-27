export default function ExportBar({ selectedCount, onExport, exporting, disabled = false }) {
  if (selectedCount === 0) return null;

  return (
    <div className="fixed bottom-0 left-0 right-0 bg-gray-900 border-t border-gray-700 p-4 flex items-center justify-between z-50">
      <p className="text-sm text-gray-300">
        <span className="font-bold text-white">{selectedCount}</span> image
        {selectedCount !== 1 ? "s" : ""} selected
      </p>
      <button
        onClick={onExport}
        disabled={exporting || disabled}
        className="px-6 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-blue-800 disabled:text-gray-400 rounded-lg font-medium transition-colors"
      >
        {exporting
          ? "Exporting..."
          : `Export ${selectedCount} Image${selectedCount !== 1 ? "s" : ""}`}
      </button>
    </div>
  );
}
