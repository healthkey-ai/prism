interface Props<K extends string> {
  options: { key: K; label: string }[]
  value: K
  onChange: (key: K) => void
  className?: string
}

/** Pill-style button strip used to switch a chart between metrics or lines. */
export default function SegmentedToggle<K extends string>({ options, value, onChange, className = 'mb-4' }: Props<K>) {
  return (
    <div className={`flex gap-1 rounded-lg border border-gray-200 p-0.5 bg-gray-50 w-fit ${className}`}>
      {options.map(o => (
        <button
          key={o.key}
          type="button"
          onClick={() => onChange(o.key)}
          aria-pressed={o.key === value}
          className={`px-4 py-1.5 text-xs rounded-md font-semibold transition-colors ${
            o.key === value ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}
