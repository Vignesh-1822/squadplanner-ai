import { MapPin } from "lucide-react"

/* Decorative world-map grid — lightweight SVG dots on a canvas.
   Replace with react-simple-maps or Mapbox when real geo data is available. */

const dots = [
  { cx: "18%", cy: "35%", label: "NYC" },
  { cx: "22%", cy: "55%", label: "Rio" },
  { cx: "48%", cy: "28%", label: "Paris" },
  { cx: "52%", cy: "42%", label: "Cairo" },
  { cx: "62%", cy: "38%", label: "Mumbai" },
  { cx: "78%", cy: "45%", label: "Bangkok" },
  { cx: "85%", cy: "52%", label: "Bali" },
  { cx: "88%", cy: "30%", label: "Tokyo" },
]

const lines = [
  { x1: "18%", y1: "35%", x2: "48%", y2: "28%" },
  { x1: "48%", y1: "28%", x2: "88%", y2: "30%" },
  { x1: "48%", y1: "28%", x2: "52%", y2: "42%" },
  { x1: "62%", y1: "38%", x2: "78%", y2: "45%" },
]

const DestinationsMap = ({ visitedDestinations = [] }) => (
  <div className="glass-card relative overflow-hidden w-full h-full min-h-[260px]">
    {/* Subtle grid background */}
    <div
      className="absolute inset-0 opacity-10"
      style={{
        backgroundImage:
          "repeating-linear-gradient(0deg, var(--outline) 0, var(--outline) 1px, transparent 1px, transparent 40px), repeating-linear-gradient(90deg, var(--outline) 0, var(--outline) 1px, transparent 1px, transparent 40px)",
      }}
    />

    {/* Radial halo */}
    <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_60%_40%,rgba(209,249,77,0.08)_0%,transparent_65%)]" />

    <svg className="absolute inset-0 w-full h-full" xmlns="http://www.w3.org/2000/svg">
      {lines.map((l, i) => (
        <line
          key={i}
          x1={l.x1} y1={l.y1} x2={l.x2} y2={l.y2}
          stroke="var(--primary)"
          strokeWidth="1"
          strokeDasharray="4 4"
          opacity="0.4"
        />
      ))}
    </svg>

    {/* Destination dots */}
    {dots.map((d, i) => (
      <div
        key={i}
        className="absolute group"
        style={{ left: d.cx, top: d.cy, transform: "translate(-50%,-50%)" }}
      >
        <div className="relative">
          <div className="w-3 h-3 rounded-full bg-primary border-2 border-surface-bright shadow-sm" />
          <div className="w-3 h-3 rounded-full bg-primary absolute inset-0 animate-ping opacity-40" />
          <span className="absolute left-4 top-1/2 -translate-y-1/2 text-[10px] font-bold text-on-surface whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity bg-surface-bright/90 px-1.5 py-0.5 rounded-md shadow-sm">
            {d.label}
          </span>
        </div>
      </div>
    ))}

    {/* Footer label */}
    <div className="absolute bottom-3 left-4 flex items-center gap-1.5">
      <MapPin size={12} className="text-primary" />
      <span className="text-xs font-bold text-on-surface-variant">
        {visitedDestinations.length || dots.length} destinations
      </span>
    </div>
  </div>
)

export default DestinationsMap
