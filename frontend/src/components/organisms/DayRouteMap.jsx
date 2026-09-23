import { useEffect, useState } from "react"
import { Map as MapIcon, Maximize2, X, Navigation } from "lucide-react"
import RouteMap from "@/molecules/RouteMap"
import { googleMapsDirections, appleMapsDirections, prefersAppleMaps } from "@/lib/mapLinks"

/**
 * The day's stops on a real map, with the walk between them drawn from the routing polylines.
 *
 * The inline map is deliberately non-interactive so it never swallows page scroll; expanding
 * opens a full-screen view where panning and zooming are the point.
 */
const DayRouteMap = ({ stops, legs }) => {
  const [expanded, setExpanded] = useState(false)
  const appleFirst = prefersAppleMaps()

  // Escape closes the overlay, and the page behind it must not scroll while it is open.
  useEffect(() => {
    if (!expanded) return undefined
    const onKey = (event) => event.key === "Escape" && setExpanded(false)
    window.addEventListener("keydown", onKey)
    document.body.style.overflow = "hidden"
    return () => {
      window.removeEventListener("keydown", onKey)
      document.body.style.overflow = ""
    }
  }, [expanded])

  if (!stops.length) return null

  return (
    <>
      <section className="bg-white/60 backdrop-blur-md rounded-2xl border border-white/70 shadow-sm overflow-hidden">
        <header className="flex items-center justify-between gap-2 px-5 pt-5 pb-3">
          <h2 className="flex items-center gap-2 text-sm font-black text-slate-900 uppercase tracking-wider">
            <MapIcon size={16} className="text-primary" />
            Day route
          </h2>
          <button
            type="button"
            onClick={() => setExpanded(true)}
            className="flex items-center gap-1.5 text-[10px] font-black uppercase tracking-widest text-slate-400 hover:text-slate-900 transition-colors cursor-pointer"
          >
            Expand
            <Maximize2 size={12} />
          </button>
        </header>

        <button
          type="button"
          onClick={() => setExpanded(true)}
          className="block w-full mx-5 rounded-xl overflow-hidden cursor-pointer"
          style={{ width: "calc(100% - 2.5rem)" }}
          aria-label="Expand the day route map"
        >
          <RouteMap stops={stops} legs={legs} height="11rem" />
        </button>

        <ol className="p-5 space-y-2.5">
          {stops.map((stop) => (
            <li key={`${stop.order}-${stop.name}`} className="flex items-center gap-3">
              <span className="size-5 shrink-0 rounded-full bg-primary/25 text-slate-800 text-[10px] font-black flex items-center justify-center">
                {stop.order}
              </span>
              <span className="text-xs font-bold text-slate-600 truncate flex-1">{stop.name}</span>
              <a
                href={appleFirst ? appleMapsDirections(stop) : googleMapsDirections(stop)}
                target="_blank"
                rel="noreferrer noopener"
                title="Get directions"
                className="shrink-0 text-slate-300 hover:text-primary-dim transition-colors"
              >
                <Navigation size={13} />
              </a>
            </li>
          ))}
        </ol>
      </section>

      {expanded && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex flex-col p-4 md:p-8">
          <div className="flex items-center justify-between gap-3 mb-3">
            <h2 className="text-white font-black text-lg tracking-tight">Day route</h2>
            <button
              type="button"
              onClick={() => setExpanded(false)}
              className="p-2 rounded-full bg-white/15 text-white hover:bg-white/25 transition-colors cursor-pointer"
              aria-label="Close the map"
            >
              <X size={18} />
            </button>
          </div>
          <div className="flex-1 rounded-2xl overflow-hidden shadow-xl">
            <RouteMap stops={stops} legs={legs} height="100%" interactive />
          </div>
          <p className="text-white/50 text-[11px] font-medium text-center mt-3">
            Tap a pin for directions · Esc to close
          </p>
        </div>
      )}
    </>
  )
}

export default DayRouteMap
