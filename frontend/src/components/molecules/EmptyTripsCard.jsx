import { Link } from "react-router-dom"
import { PlusCircle, MapPin } from "lucide-react"

const EmptyTripsCard = () => (
  <div className="flex flex-col items-center justify-center h-full min-h-[180px] rounded-2xl border-2 border-dashed border-outline/40 p-6 text-center">
    <div className="w-12 h-12 rounded-full bg-surface-container-low flex items-center justify-center mb-3">
      <MapPin size={20} className="text-on-surface-variant" />
    </div>
    <p className="text-sm font-bold text-on-surface">No trips yet</p>
    <p className="text-xs text-on-surface-variant mt-1 mb-4">
      Start planning your first squad adventure
    </p>
    <Link
      to="/trips/new"
      className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-primary text-black text-xs font-bold volt-glow hover:bg-primary-dim transition-colors"
    >
      <PlusCircle size={13} />
      Plan a Trip
    </Link>
  </div>
)

export default EmptyTripsCard
