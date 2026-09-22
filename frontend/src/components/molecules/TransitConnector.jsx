import { Footprints, Train, Car, Bike } from "lucide-react"
import { transitLabel } from "@/lib/itinerary"

const MODE_ICON = { WALK: Footprints, TRANSIT: Train, DRIVE: Car, BICYCLE: Bike }

/** The leg between two stops — how long it takes to get from one to the next. */
const TransitConnector = ({ leg }) => {
  const label = transitLabel(leg)
  if (!label) return null

  const Icon = MODE_ICON[leg.mode] || Footprints

  return (
    <div className="flex items-center gap-3 pl-6 py-1.5">
      <span className="w-px h-8 bg-slate-200" />
      <span className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-slate-400">
        <Icon size={12} className="text-primary" />
        {label}
      </span>
    </div>
  )
}

export default TransitConnector
