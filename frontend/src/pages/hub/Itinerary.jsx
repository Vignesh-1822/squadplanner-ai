import { useState } from "react"
import { useOutletContext, useParams } from "react-router-dom"
import { Wallet, Footprints } from "lucide-react"
import DayPills from "@/molecules/DayPills"
import DayTimeline from "@/organisms/DayTimeline"
import DayRouteMap from "@/organisms/DayRouteMap"
import DaySummary from "@/organisms/DaySummary"
import RefinementBox from "@/organisms/RefinementBox"
import { dayTitle, formatDayDate, formatMoney, dayDistanceKm, dayStops } from "@/lib/itinerary"

const ItineraryTab = () => {
  const { tripId } = useParams()
  const result = useOutletContext()
  const days = result?.itinerary?.days || []
  const [activeDay, setActiveDay] = useState(days[0]?.day_number ?? 1)

  if (!days.length) {
    return (
      <p className="text-slate-400 text-sm font-medium py-16 text-center">
        This trip has no itinerary days.
      </p>
    )
  }

  const day = days.find((candidate) => candidate.day_number === activeDay) || days[0]
  const distance = dayDistanceKm(day)

  return (
    <div className="space-y-5">
      <DayPills days={days} activeDay={day.day_number} onSelect={setActiveDay} />

      {/* Day banner */}
      <section className="flex flex-wrap items-center justify-between gap-4 bg-white/50 backdrop-blur-md rounded-2xl border border-white/70 p-5">
        <div className="flex items-center gap-4">
          <span className="size-12 shrink-0 rounded-xl bg-primary flex items-center justify-center text-slate-900 text-lg font-black">
            {String(day.day_number).padStart(2, "0")}
          </span>
          <div>
            <h2 className="text-xl font-black text-slate-900 tracking-tight leading-none">
              {dayTitle(day)}
            </h2>
            <p className="text-slate-500 text-xs font-medium mt-1">{formatDayDate(day.date)}</p>
          </div>
        </div>

        <div className="flex items-center gap-5 text-[11px] font-bold uppercase tracking-wider text-slate-400">
          {distance && (
            <span className="flex items-center gap-1.5">
              <Footprints size={13} className="text-primary" />
              {distance} km
            </span>
          )}
          <span className="flex items-center gap-1.5">
            <Wallet size={13} className="text-primary" />
            {formatMoney(day.estimated_day_cost_usd)}
          </span>
        </div>
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 items-start">
        <div className="lg:col-span-2">
          <DayTimeline day={day} />
        </div>

        <aside className="space-y-4 lg:sticky lg:top-4">
          <DayRouteMap stops={dayStops(day)} />
          <DaySummary day={day} weather={result?.itinerary?.weather} />
          <RefinementBox tripId={tripId} />
        </aside>
      </div>
    </div>
  )
}

export default ItineraryTab
