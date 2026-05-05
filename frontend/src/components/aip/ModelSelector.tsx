interface Props {
  value: string
  onChange: (value: string) => void
  options: string[]
}

export default function ModelSelector({ value, onChange, options }: Props) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="px-3 py-2 border rounded-lg text-sm dark:bg-slate-700 dark:border-slate-600 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary/50"
    >
      {options.map((opt) => (
        <option key={opt} value={opt}>{opt}</option>
      ))}
    </select>
  )
}
