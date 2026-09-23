import { Wallet, Footprints, CloudSun, Clock } from "lucide-react"
import StatTile from "@/molecules/StatTile"
import { formatMoney, dayDistanceKm } from "@/lib/itinerary"

/** The dark stats card beside the timeline. */
const DaySummary = ({ day, weather }) => {
  const distance = dayDistanceKm(day)
  const travelMinutes = day?.total_travel_minutes

  return (
    <section className="bg-white/60 backdrop-blur-md rounded-2xl border border-white/70 shadow-sm p-5 space-y-4">
      <h2 className="text-sm font-black text-slate-900 uppercase tracking-wider">Day summary</h2>

      <div className="grid grid-cols-2 gap-2.5">
        <StatTile icon={Wallet} label="Day cost" value={formatMoney(day?.estimated_day_cost_usd)} />
        <StatTile icon={Footprints} label="Distance" value={distance ? `${distance} km` : "—"} />
        {travelMinutes ? (
          <StatTile icon={Clock} label="Travel time" value={`${Math.round(travelMinutes)} min`} />
        ) : null}
        {weather?.summary && weather.summary !== "Weather data unavailable" ? (
          <StatTile
            icon={CloudSun}
            label="Forecast"
            value={`${Math.round(weather.avg_temp_c)}°C`}
          />
        ) : null}
      </div>

      {day?.meals?.length > 0 && (
        <div className="pt-1 border-t border-slate-100">
          <p className="text-[10px] font-black uppercase tracking-widest text-slate-400 mb-2">Meals</p>
          <ul className="space-y-1.5">
            {day.meals.map((meal) => (
              <li key={meal} className="text-xs font-medium text-slate-500 leading-snug">
                {meal}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}

export default DaySummary
