export default function ImageCard({ image, selected, onToggle, onNameChange }) {
  return (
    <div
      className={`relative rounded-lg border-2 p-2 transition-colors cursor-pointer ${
        selected
          ? "border-blue-500 bg-blue-500/10"
          : "border-gray-700 hover:border-gray-500 bg-gray-900"
      }`}
      onClick={onToggle}
    >
      <div className="aspect-square flex items-center justify-center bg-[repeating-conic-gradient(#1f2937_0%_25%,#111827_0%_50%)] bg-[length:16px_16px] rounded overflow-hidden mb-2">
        <img
          src={`data:image/png;base64,${image.thumbnail}`}
          alt={image.name}
          className="max-w-full max-h-full object-contain"
        />
      </div>

      <div className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={selected}
          onChange={onToggle}
          onClick={(e) => e.stopPropagation()}
          className="accent-blue-500 w-4 h-4 shrink-0"
        />
        <input
          type="text"
          value={image.name}
          onChange={(e) => onNameChange(e.target.value)}
          onClick={(e) => e.stopPropagation()}
          className="bg-gray-800 border border-gray-600 rounded px-2 py-1 text-sm w-full text-white focus:outline-none focus:border-blue-500"
        />
      </div>
      <p className="text-xs text-gray-500 mt-1 text-right">
        {image.width} x {image.height}px
      </p>
    </div>
  );
}
