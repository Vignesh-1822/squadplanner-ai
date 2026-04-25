const valueToLevel = (v) => {
  if (v <= 25) return "CHILL"
  if (v <= 50) return "MODERATE"
  if (v <= 75) return "INTENSE"
  return "HIGH PRIORITY"
}

const PreferenceSlider = ({ label, value, onChange }) => {
  const level = valueToLevel(value)

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold text-gray-700">{label}</span>
        <span className="text-[10px] font-black uppercase tracking-widest text-gray-400">{level}</span>
      </div>
      <input
        type="range"
        min={0}
        max={100}
        step={25}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full h-1.5 rounded-full appearance-none cursor-pointer"
        style={{ accentColor: "var(--primary)" }}
      />
    </div>
  )
}

export default PreferenceSlider
