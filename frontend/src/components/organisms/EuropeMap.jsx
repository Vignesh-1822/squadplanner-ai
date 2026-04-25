/* Stylized Europe map — simplified SVG shapes inspired by the Ro.mly design.
   Countries are color-coded: planned (volt yellow), visited (pink), not visited (light gray).
   Replace with react-simple-maps for real geo data. */

const CITIES = [
  { x: 245, y: 148, name: "Paris" },
  { x: 355, y: 225, name: "Milano" },
  { x: 290, y: 280, name: "Barcelona" },
]

const EuropeMap = () => (
  <div className="bg-white/40 backdrop-blur-md rounded-2xl p-4 h-full border border-white/50 flex flex-col">
    {/* Header */}
    <div className="flex items-center justify-between mb-3">
      <div className="flex items-center gap-1.5 text-xs text-on-surface-variant font-semibold">
        <span>🗺</span> Map
      </div>
      <button className="text-xs text-on-surface-variant hover:text-on-surface border border-outline/40 px-2.5 py-1 rounded-full">
        All countries ↓
      </button>
    </div>

    {/* SVG map */}
    <div className="flex-1 relative">
      <svg viewBox="0 0 500 340" className="w-full h-full" xmlns="http://www.w3.org/2000/svg">
        {/* France - planned (volt yellow) */}
        <path
          d="M200,100 L240,90 L280,110 L285,150 L260,175 L220,170 L195,145 Z"
          fill="#d1f94d" fillOpacity="0.7" stroke="white" strokeWidth="2"
        />
        {/* Spain - visited (pink) */}
        <path
          d="M170,170 L220,170 L260,175 L255,215 L230,235 L190,230 L160,210 L155,185 Z"
          fill="#ffb3c6" fillOpacity="0.7" stroke="white" strokeWidth="2"
        />
        {/* Italy - visited (pink) */}
        <path
          d="M285,150 L320,135 L350,160 L360,195 L340,230 L320,240 L300,210 L290,185 L285,165 Z"
          fill="#ffb3c6" fillOpacity="0.7" stroke="white" strokeWidth="2"
        />
        {/* Germany - not visited (gray) */}
        <path
          d="M240,90 L290,75 L320,100 L315,130 L285,150 L260,140 L240,120 Z"
          fill="#e2e3d0" fillOpacity="0.8" stroke="white" strokeWidth="2"
        />
        {/* UK - not visited */}
        <path
          d="M155,65 L185,55 L195,80 L180,95 L160,90 Z"
          fill="#e2e3d0" fillOpacity="0.8" stroke="white" strokeWidth="2"
        />
        {/* Portugal */}
        <path
          d="M155,185 L170,185 L170,220 L158,225 L150,210 Z"
          fill="#ffb3c6" fillOpacity="0.7" stroke="white" strokeWidth="2"
        />
        {/* Switzerland/Austria */}
        <path
          d="M260,140 L285,150 L290,165 L270,168 L255,155 Z"
          fill="#e2e3d0" fillOpacity="0.8" stroke="white" strokeWidth="2"
        />

        {/* City dots */}
        {CITIES.map(({ x, y, name }) => (
          <g key={name}>
            <circle cx={x} cy={y} r="5" fill="var(--on-surface)" />
            <circle cx={x} cy={y} r="2.5" fill="white" />
            <text x={x + 8} y={y + 4} fontSize="9" fill="var(--on-surface)" fontWeight="600">{name}</text>
          </g>
        ))}
      </svg>
    </div>

    {/* Legend */}
    <div className="flex items-center gap-4 mt-2 text-[11px] text-on-surface-variant">
      {[
        { color: "#d1f94d", label: "Planned" },
        { color: "#ffb3c6", label: "Visited" },
        { color: "#e2e3d0", label: "Not visited" },
      ].map(({ color, label }) => (
        <div key={label} className="flex items-center gap-1">
          <div className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: color }} />
          {label}
        </div>
      ))}
    </div>
  </div>
)

export default EuropeMap
