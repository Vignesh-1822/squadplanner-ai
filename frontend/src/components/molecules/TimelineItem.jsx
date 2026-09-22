import { Star, MapPin, UtensilsCrossed, Mountain, Building2, Martini, ShoppingBag, Landmark, Camera } from "lucide-react"
import { priceLabel } from "@/lib/itinerary"

// Categories come from the agent's tool selection; meals arrive as their own schedule type.
const CATEGORY_ICON = {
  food: UtensilsCrossed,
  outdoor: Mountain,
  urban: Building2,
  nightlife: Martini,
  shopping: ShoppingBag,
  culture: Landmark,
}

const TimelineItem = ({ item }) => {
  const { time, label, notes, type, activity } = item
  const Icon = type === "meal" ? UtensilsCrossed : CATEGORY_ICON[activity?.category] || Camera
  const tags = (activity?.tags || []).slice(0, 3)

  return (
    <article className="flex gap-4">
      {/* Clock rail */}
      <div className="shrink-0 w-14 pt-4 text-right">
        <span className="text-xs font-black text-slate-900 tabular-nums">{time || "—"}</span>
      </div>

      <div className="flex-1 bg-white/60 backdrop-blur-md rounded-2xl border border-white/70 shadow-sm p-5 hover:shadow-md transition-shadow">
        <div className="flex items-start justify-between gap-3 mb-2">
          <div className="flex items-center gap-2 min-w-0">
            <span className="size-8 rounded-lg bg-primary/20 flex items-center justify-center shrink-0">
              <Icon size={15} className="text-slate-800" />
            </span>
            <div className="min-w-0">
              <p className="text-[10px] font-black uppercase tracking-widest text-slate-400 leading-none mb-1">
                {type === "meal" ? "Meal" : activity?.category || "Stop"}
              </p>
              <h3 className="font-black text-slate-900 leading-tight truncate">
                {activity?.name || label}
              </h3>
            </div>
          </div>

          {activity && (
            <span className="shrink-0 px-2 py-0.5 rounded-full bg-primary/20 text-slate-800 text-[10px] font-black tracking-widest">
              {priceLabel(activity.price_level)}
            </span>
          )}
        </div>

        {/* No per-activity prose exists in the payload, so the card shows what the agent
            actually knows about the place rather than inventing copy. */}
        {notes && <p className="text-slate-500 text-sm font-medium leading-relaxed">{notes}</p>}

        {activity && (
          <div className="mt-3 space-y-2">
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] font-bold text-slate-400">
              {activity.rating > 0 && (
                <span className="flex items-center gap-1">
                  <Star size={11} className="text-primary fill-primary" />
                  {activity.rating.toFixed(1)}
                </span>
              )}
              {activity.address && (
                <span className="flex items-center gap-1 min-w-0">
                  <MapPin size={11} className="text-primary shrink-0" />
                  <span className="truncate">{activity.address}</span>
                </span>
              )}
            </div>

            {tags.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {tags.map((tag) => (
                  <span
                    key={tag}
                    className="px-2 py-0.5 rounded-full bg-slate-100 text-slate-500 text-[10px] font-bold capitalize"
                  >
                    {String(tag).replace(/_/g, " ")}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </article>
  )
}

export default TimelineItem
