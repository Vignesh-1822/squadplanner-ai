import { useState } from "react"
import { ArrowRight, MapPin, Plane } from "lucide-react"

// Photography is resolved server-side (Wikipedia, with Unsplash as fallback). These gradients
// are the fallback for destinations where nothing resolved, and for images that fail to load.
const TYPE_GRADIENTS = {
  major_city: "from-slate-800 via-slate-700 to-slate-900",
  small_city: "from-slate-700 via-slate-600 to-slate-800",
  town: "from-amber-700 via-amber-600 to-orange-800",
  mountain_town: "from-emerald-800 via-teal-700 to-slate-800",
  national_park: "from-green-800 via-emerald-700 to-teal-900",
  state_park: "from-green-700 via-green-600 to-emerald-800",
  natural_area: "from-lime-800 via-green-700 to-emerald-900",
  beach_town: "from-cyan-600 via-sky-500 to-blue-700",
  island: "from-teal-500 via-cyan-600 to-blue-700",
  resort_town: "from-rose-600 via-pink-600 to-purple-700",
}

const COST_LABEL = { low: "$", medium: "$$", high: "$$$" }

const TYPE_LABEL = {
  major_city: "Major city",
  small_city: "City",
  town: "Town",
  mountain_town: "Mountain town",
  national_park: "National park",
  state_park: "State park",
  natural_area: "Natural area",
  beach_town: "Beach town",
  island: "Island",
  resort_town: "Resort town",
}

const DestinationCard = ({ destination, matchPercent, onSelect, onViewDetails, disabled }) => {
  const { name, state, type, llm_reasoning: reasoning, cost_level: costLevel } = destination
  const gradient = TYPE_GRADIENTS[type] || "from-slate-700 via-slate-600 to-slate-800"
  const airport = destination.nearest_airports?.[0]
  const [imageFailed, setImageFailed] = useState(false)
  const showImage = !!destination.image_url && !imageFailed

  return (
    <div className="bg-white/60 backdrop-blur-md rounded-2xl border border-white/70 shadow-sm overflow-hidden flex flex-col hover:shadow-md transition-shadow">
      <div className={`relative h-40 bg-gradient-to-br ${gradient} flex items-end p-4 overflow-hidden`}>
        {showImage && (
          <>
            <img
              src={destination.image_url}
              alt={name}
              loading="lazy"
              onError={() => setImageFailed(true)}
              className="absolute inset-0 w-full h-full object-cover"
            />
            {/* Keeps the badge and type label legible over an unpredictable photo. */}
            <div className="absolute inset-0 bg-gradient-to-t from-slate-900/70 via-slate-900/10 to-slate-900/20" />
          </>
        )}
        <span className="absolute top-3 left-3 z-10 px-2.5 py-1 rounded-full bg-primary text-slate-900 text-[10px] font-black uppercase tracking-widest shadow-sm">
          {matchPercent}% Match
        </span>
        <span className="relative z-10 text-white/90 text-[10px] font-bold uppercase tracking-widest">
          {TYPE_LABEL[type] || type}
        </span>
      </div>

      <div className="p-5 flex flex-col gap-3 flex-1">
        <div className="flex items-start justify-between gap-2">
          <h3 className="text-lg font-black text-slate-900 leading-tight">
            {name}
            {state && <span className="text-slate-400">, {state}</span>}
          </h3>
          <span className="shrink-0 px-2 py-0.5 rounded-full bg-primary/20 text-slate-800 text-[10px] font-black tracking-widest">
            {COST_LABEL[costLevel] || "$$"}
          </span>
        </div>

        <p className="text-slate-500 text-sm font-medium leading-relaxed line-clamp-4 flex-1">
          {reasoning}
        </p>

        <div className="flex items-center gap-3 text-[11px] font-bold uppercase tracking-wider text-slate-400">
          {airport && (
            <span className="flex items-center gap-1.5">
              <Plane size={12} className="text-primary" />
              {airport.code}
            </span>
          )}
          <span className="flex items-center gap-1.5">
            <MapPin size={12} className="text-primary" />
            {state || "US"}
          </span>
        </div>

        <div className="flex flex-col gap-2">
          <button
            type="button"
            onClick={() => onSelect(destination)}
            disabled={disabled}
            className="group w-full flex items-center justify-center gap-2 bg-primary text-slate-900 font-black text-[11px] uppercase tracking-widest px-5 py-3 rounded-xl transition-all hover:brightness-105 active:scale-95 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Select This Destination
            <ArrowRight size={14} className="transition-transform group-hover:translate-x-1" />
          </button>
          <button
            type="button"
            onClick={() => onViewDetails(destination)}
            className="w-full text-center text-[11px] font-bold uppercase tracking-widest text-slate-400 hover:text-slate-900 py-2 transition-colors cursor-pointer"
          >
            View Details
          </button>
        </div>
      </div>
    </div>
  )
}

export default DestinationCard
