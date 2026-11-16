import { X, Plane, Car, ArrowRight } from "lucide-react"

const VIBE_LABELS = {
  outdoor: "Nature & Outdoors",
  food: "Food & Dining",
  nightlife: "Nightlife",
  urban: "Urban Exploration",
  shopping: "Shopping",
}

const COST_COPY = {
  low: "Budget friendly",
  medium: "Mid range",
  high: "Premium",
}

/**
 * The detail panel behind "View Details" at the destination choice.
 *
 * Deliberately not an itinerary: the graph is paused *before* flights, hotels and activities are
 * fetched, so no itinerary exists for any candidate yet. Building one for all five would mean
 * five full pipeline runs per trip. This shows what the agent actually knows at this point.
 */
const DestinationDetail = ({ destination, matchPercent, onSelect, onClose, disabled }) => {
  if (!destination) return null

  const { name, state, llm_reasoning: reasoning, cost_level: costLevel, notes } = destination
  const bestFor = destination.best_for || []
  const vibeTags = destination.vibe_tags || {}
  const airports = destination.nearest_airports || []

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-[2rem] shadow-xl w-full max-w-2xl max-h-[85vh] overflow-y-auto"
        onClick={(event) => event.stopPropagation()}
      >
        {destination.image_url && (
          <div className="relative h-56 w-full overflow-hidden">
            <img src={destination.image_url} alt={name} className="w-full h-full object-cover" />
            {/* Both Wikimedia (CC) and Unsplash require the source to be credited. */}
            {destination.image_credit && (
              <a
                href={destination.image_link || undefined}
                target="_blank"
                rel="noreferrer noopener"
                className="absolute bottom-2 right-3 text-[10px] font-medium text-white/70 hover:text-white transition-colors"
              >
                {destination.image_credit} / {destination.image_source}
              </a>
            )}
          </div>
        )}

        <div className="sticky top-0 bg-white/95 backdrop-blur-md px-8 pt-8 pb-5 border-b border-slate-100 flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="px-2.5 py-1 rounded-full bg-primary text-slate-900 text-[10px] font-black uppercase tracking-widest">
                {matchPercent}% Match
              </span>
              <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400">
                {COST_COPY[costLevel] || costLevel}
              </span>
            </div>
            <h2 className="text-3xl font-black text-slate-900 tracking-tight leading-none">
              {name}
              {state && <span className="text-slate-400">, {state}</span>}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-2 rounded-full text-slate-400 hover:text-slate-900 hover:bg-slate-100 transition-colors cursor-pointer shrink-0"
          >
            <X size={18} />
          </button>
        </div>

        <div className="px-8 py-6 space-y-7">
          <section>
            <h3 className="text-[11px] font-black uppercase tracking-widest text-slate-400 mb-2">
              Why your squad
            </h3>
            <p className="text-slate-600 font-medium leading-relaxed">{reasoning}</p>
            {notes && <p className="text-slate-500 text-sm font-medium leading-relaxed mt-2">{notes}</p>}
          </section>

          {bestFor.length > 0 && (
            <section>
              <h3 className="text-[11px] font-black uppercase tracking-widest text-slate-400 mb-3">Best for</h3>
              <div className="flex flex-wrap gap-2">
                {bestFor.map((tag) => (
                  <span
                    key={tag}
                    className="px-3 py-1.5 rounded-full bg-primary/15 text-slate-700 text-xs font-bold capitalize"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </section>
          )}

          {Object.keys(vibeTags).length > 0 && (
            <section>
              <h3 className="text-[11px] font-black uppercase tracking-widest text-slate-400 mb-3">
                The vibe
              </h3>
              <div className="space-y-2.5">
                {Object.entries(vibeTags).map(([key, value]) => (
                  <div key={key} className="flex items-center gap-3">
                    <span className="w-40 shrink-0 text-xs font-bold text-slate-600">
                      {VIBE_LABELS[key] || key}
                    </span>
                    <div className="flex-1 h-2 rounded-full bg-slate-100 overflow-hidden">
                      <div
                        className="h-full rounded-full bg-primary"
                        style={{ width: `${Math.round(Number(value) * 100)}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {airports.length > 0 && (
            <section>
              <h3 className="text-[11px] font-black uppercase tracking-widest text-slate-400 mb-3">
                Getting there
              </h3>
              <div className="space-y-2">
                {airports.map((airport) => (
                  <div
                    key={airport.code}
                    className="flex items-center justify-between gap-4 p-3 rounded-xl bg-slate-50"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <Plane size={14} className="text-primary shrink-0" />
                      <span className="font-black text-slate-900 text-sm shrink-0">{airport.code}</span>
                      <span className="text-slate-500 text-xs font-medium truncate">{airport.name}</span>
                    </div>
                    {airport.drive_min != null && (
                      <span className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-slate-400 shrink-0">
                        <Car size={12} />
                        {airport.drive_min} min
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>

        <div className="sticky bottom-0 bg-white/95 backdrop-blur-md px-8 py-5 border-t border-slate-100">
          <button
            type="button"
            onClick={() => onSelect(destination)}
            disabled={disabled}
            className="group w-full flex items-center justify-center gap-2 bg-primary text-slate-900 font-black text-xs uppercase tracking-widest px-6 py-3.5 rounded-xl transition-all hover:brightness-105 active:scale-95 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Select This Destination
            <ArrowRight size={14} className="transition-transform group-hover:translate-x-1" />
          </button>
        </div>
      </div>
    </div>
  )
}

export default DestinationDetail
