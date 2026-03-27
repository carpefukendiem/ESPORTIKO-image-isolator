import ImageCard from "./ImageCard";

export default function ImageGrid({
  images,
  selectedIds,
  onToggle,
  onNameChange,
  onSelectAll,
  onDeselectAll,
}) {
  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">
          Detected Images ({images.length})
        </h2>
        <div className="flex gap-2">
          <button
            onClick={onSelectAll}
            className="px-3 py-1 text-sm bg-gray-700 hover:bg-gray-600 rounded transition-colors"
          >
            Select All
          </button>
          <button
            onClick={onDeselectAll}
            className="px-3 py-1 text-sm bg-gray-700 hover:bg-gray-600 rounded transition-colors"
          >
            Deselect All
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
        {images.map((img) => (
          <ImageCard
            key={img.id}
            image={img}
            selected={selectedIds.has(img.id)}
            onToggle={() => onToggle(img.id)}
            onNameChange={(name) => onNameChange(img.id, name)}
          />
        ))}
      </div>
    </div>
  );
}
