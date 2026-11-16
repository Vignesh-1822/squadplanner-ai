import { useOutletContext } from "react-router-dom"
import { Hotel, Star, CheckCircle2, AlertTriangle, ShieldCheck } from "lucide-react"
import SquadPanel from "@/organisms/SquadPanel"
import TripStats from "@/organisms/TripStats"
import NextUpWidget from "@/organisms/NextUpWidget"
import TripVibe from "@/organisms/TripVibe"
import LocationMapCard from "@/organisms/LocationMapCard"
import { formatMoney } from "@/lib/itinerary"

/**
 * Stitch Trip Hub Overview tab:
 * 5-widget grid faithfully matching Stitch screen 'Trip Hub Overview'
 * (The Squad, Quick Stats, Next Up, Trip Vibe with SVG radar, and Location Map Card)
 * plus companion Lodging & Squad Requirements sections.
 */
const OverviewTab = () => {
  const result = useOutletContext()
  const itinerary = result?.itinerary || {}
  const hotel = itinerary.hotel
  const destination = itinerary.selected_destination || result?.trip_name || "Destination"

  // Shape is { passed, satisfied[], unmet[], warnings[] }
  const satisfaction = itinerary.constraint_satisfaction || {}
  const requirements = [
    ...(satisfaction.satisfied || []).map((text) => ({ text, met: true })),
    ...(satisfaction.unmet || []).map((text) => ({ text, met: false })),
    ...(satisfaction.warnings || []).map((text) => ({ text, met: false })),
  ]

  return (
    <div className="space-y-6 pb-6">
      {/* Stitch 5-Widget Bento Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 items-stretch">
        {/* Widget 1: The Squad */}
        <SquadPanel
          members={itinerary.members || []}
          flights={itinerary.flights || []}
        />

        {/* Widget 2: Quick Stats */}
        <TripStats itinerary={itinerary} />

        {/* Widget 3: Next Up (Solid Volt Card) */}
        <NextUpWidget itinerary={itinerary} />

        {/* Widget 4: Trip Vibe with SVG Radar Chart (2 cols) */}
        <TripVibe members={itinerary.members || []} />

        {/* Widget 5: Location Map Card (1 col) */}
        <LocationMapCard
          destination={destination}
          days={itinerary.days || []}
        />
      </div>

      {/* Companion Section: Detailed Lodging & Squad Constraints Checklist */}
      {(hotel || requirements.length > 0) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-2">
          {hotel && (
            <section className="bg-white/60 backdrop-blur-xl rounded-3xl border border-white/70 shadow-sm p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="flex items-center gap-2 text-sm font-black text-slate-900 uppercase tracking-wider">
                  <Hotel size={18} className="text-primary fill-primary" />
                  Lodging Details
                </h3>
                {hotel.rating > 0 && (
                  <span className="flex items-center gap-1 text-xs font-black text-slate-700 bg-slate-100 px-2.5 py-1 rounded-full">
                    <Star size={12} className="text-amber-500 fill-amber-500" />
                    {hotel.rating.toFixed(1)}
                  </span>
                )}
              </div>

              <h4 className="font-black text-slate-900 text-lg leading-snug">
                {hotel.name}
              </h4>
              <p className="text-slate-500 text-xs font-medium mt-1 line-clamp-2">
                {hotel.address || "Confirmed squad accommodation"}
              </p>

              <div className="flex items-end justify-between gap-3 mt-5 pt-4 border-t border-slate-100">
                <div>
                  <p className="text-2xl font-black text-slate-900 leading-none">
                    {formatMoney(hotel.total_price_usd)}
                  </p>
                  <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mt-1">
                    {formatMoney(hotel.price_per_night_usd)} / night
                  </p>
                </div>
                <span className="text-[10px] font-black text-green-700 bg-green-100 px-3 py-1.5 rounded-full uppercase tracking-wider">
                  Confirmed
                </span>
              </div>
            </section>
          )}

          {requirements.length > 0 && (
            <section className="bg-white/60 backdrop-blur-xl rounded-3xl border border-white/70 shadow-sm p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="flex items-center gap-2 text-sm font-black text-slate-900 uppercase tracking-wider">
                  <ShieldCheck size={18} className="text-primary fill-primary" />
                  Squad Requirements
                </h3>
                {satisfaction.passed && (
                  <span className="px-2.5 py-1 rounded-full bg-primary text-slate-900 text-[10px] font-black uppercase tracking-wider">
                    All met
                  </span>
                )}
              </div>

              <ul className="space-y-2.5 max-h-[160px] overflow-y-auto pr-1">
                {requirements.map(({ text, met }, index) => (
                  <li
                    key={index}
                    className="flex items-start gap-2.5 text-xs font-medium text-slate-700 leading-relaxed"
                  >
                    {met ? (
                      <CheckCircle2
                        size={15}
                        className="text-green-600 shrink-0 mt-0.5"
                      />
                    ) : (
                      <AlertTriangle
                        size={15}
                        className="text-amber-500 shrink-0 mt-0.5"
                      />
                    )}
                    <span>{text}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      )}
    </div>
  )
}

export default OverviewTab
