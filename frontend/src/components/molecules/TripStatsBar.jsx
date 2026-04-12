const stats = [
  { value: "58", label: "Travel Days" },
  { value: "4",  label: "Countries Visited" },
  { value: "7",  label: "Trips Planned" },
]

const TripStatsBar = ({ items = stats }) => (
  <div className="flex flex-col gap-3">
    {items.map(({ value, label }) => (
      <div key={label}>
        <span className="text-2xl font-black text-on-surface leading-none">{value}</span>
        <p className="text-[11px] text-on-surface-variant mt-0.5">{label}</p>
      </div>
    ))}
  </div>
)

export default TripStatsBar
