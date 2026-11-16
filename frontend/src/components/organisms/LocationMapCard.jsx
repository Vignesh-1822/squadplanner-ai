import { Map } from "lucide-react"
import { useNavigate, useParams } from "react-router-dom"

/**
 * Stitch Quick Location / Map Card:
 * Centered glass card, circular map icon button with hover volt background,
 * underline link navigating to the itinerary map view, and dynamic neighborhood tags.
 */
const LocationMapCard = ({ destination = "City", days = [] }) => {
  const navigate = useNavigate()
  const { tripId } = useParams()

  // Extract distinct neighborhood names from days
  const neighborhoods = Array.from(
    new Set(
      days
        .map((day) => day.neighborhood)
        .filter(Boolean)
        .map((n) => n.split(/[,&]/)[0].trim()),
    ),
  ).slice(0, 3)

  return (
    <section className="bg-white/60 backdrop-blur-xl rounded-3xl border border-white/70 shadow-sm p-6 flex flex-col items-center justify-center text-center group min-h-[280px]">
      <div className="size-20 bg-slate-100/90 rounded-full mb-4 flex items-center justify-center group-hover:bg-primary group-hover:scale-105 transition-all duration-300 shadow-inner">
        <Map
          size={32}
          className="text-slate-400 group-hover:text-slate-900 transition-colors"
        />
      </div>

      <h3 className="font-black text-lg text-slate-900 tracking-tight mb-1">
        {destination} Map
      </h3>
      <p className="text-xs text-slate-500 max-w-xs mb-5">
        Check your saved locations and commute routes.
      </p>

      <button
        type="button"
        onClick={() => navigate(`/trips/${tripId}/hub/itinerary`)}
        className="text-slate-900 font-black text-sm underline decoration-primary decoration-4 underline-offset-4 hover:opacity-75 transition-opacity cursor-pointer"
      >
        Open Maps View
      </button>

      {neighborhoods.length > 0 && (
        <div className="mt-5 flex flex-wrap justify-center gap-2">
          {neighborhoods.map((name) => (
            <span
              key={name}
              className="bg-slate-100 text-slate-700 text-[10px] font-black px-3 py-1 rounded-full uppercase tracking-wider"
            >
              {name}
            </span>
          ))}
        </div>
      )}
    </section>
  )
}

export default LocationMapCard
