import { Map as MapIcon } from "lucide-react"

/**
 * A stylised route sketch for the day, matching the design's map preview.
 *
 * Deliberately not a real map: the mock draws pins and a dashed connector rather than tiles,
 * and this keeps a mapping library and its tile requests out of the bundle. Stops are placed by
 * normalising their coordinates into the panel, so the shape reflects the actual geography.
 */
const DayRouteMap = ({ stops }) => {
  if (!stops.length) return null

  const lats = stops.map((s) => s.lat)
  const lngs = stops.map((s) => s.lng)
  const spanLat = Math.max(...lats) - Math.min(...lats) || 1
  const spanLng = Math.max(...lngs) - Math.min(...lngs) || 1

  // 12% inset so pins never touch the edges of the panel.
  const placed = stops.map((stop) => ({
    ...stop,
    x: 12 + ((stop.lng - Math.min(...lngs)) / spanLng) * 76,
    y: 88 - ((stop.lat - Math.min(...lats)) / spanLat) * 76,
  }))

  return (
    <section className="bg-white/60 backdrop-blur-md rounded-2xl border border-white/70 shadow-sm overflow-hidden">
      <header className="flex items-center gap-2 px-5 pt-5 pb-3">
        <MapIcon size={16} className="text-primary" />
        <h2 className="text-sm font-black text-slate-900 uppercase tracking-wider">Day route</h2>
      </header>

      <div className="relative mx-5 h-44 rounded-xl bg-gradient-to-br from-slate-100 via-emerald-50 to-slate-200 overflow-hidden">
        <svg className="absolute inset-0 w-full h-full" viewBox="0 0 100 100" preserveAspectRatio="none">
          <polyline
            points={placed.map((p) => `${p.x},${p.y}`).join(" ")}
            fill="none"
            stroke="var(--primary-dim)"
            strokeWidth="0.8"
            strokeDasharray="2 2"
            vectorEffect="non-scaling-stroke"
          />
        </svg>
        {placed.map((stop) => (
          <span
            key={`${stop.order}-${stop.name}`}
            title={stop.name}
            style={{ left: `${stop.x}%`, top: `${stop.y}%` }}
            className="absolute -translate-x-1/2 -translate-y-1/2 size-6 rounded-full bg-slate-900 text-primary text-[10px] font-black flex items-center justify-center shadow-md ring-2 ring-white"
          >
            {stop.order}
          </span>
        ))}
      </div>

      <ol className="p-5 space-y-2.5">
        {stops.map((stop) => (
          <li key={`${stop.order}-${stop.name}`} className="flex items-center gap-3">
            <span className="size-5 shrink-0 rounded-full bg-primary/25 text-slate-800 text-[10px] font-black flex items-center justify-center">
              {stop.order}
            </span>
            <span className="text-xs font-bold text-slate-600 truncate">{stop.name}</span>
          </li>
        ))}
      </ol>
    </section>
  )
}

export default DayRouteMap
