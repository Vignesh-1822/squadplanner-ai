import { useState } from "react"
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

// Venue photography is not in the payload — see the note on the thumbnail below — so each
// category gets its own wash, which reads as deliberate rather than as a broken image.
const CATEGORY_WASH = {
  food: "from-amber-200 via-orange-200 to-rose-200",
  outdoor: "from-emerald-200 via-teal-200 to-green-300",
  urban: "from-slate-300 via-slate-200 to-zinc-300",
  nightlife: "from-purple-300 via-fuchsia-200 to-indigo-300",
  shopping: "from-pink-200 via-rose-200 to-orange-200",
  culture: "from-amber-200 via-yellow-200 to-lime-200",
}

const TimelineItem = ({ item }) => {
  const { time, label, notes, type, activity } = item
  const Icon = type === "meal" ? UtensilsCrossed : CATEGORY_ICON[activity?.category] || Camera
  const tags = (activity?.tags || []).slice(0, 3)
  const wash = CATEGORY_WASH[type === "meal" ? "food" : activity?.category] || CATEGORY_WASH.urban
  const [imageFailed, setImageFailed] = useState(false)
  // Meals carry their photo on the day rather than on an activity — they have no place_id.
  const imageUrl = activity?.image_url || item.image?.image_url
  const showImage = !!imageUrl && !imageFailed

  return (
    <article className="flex gap-4">
      {/* Clock rail */}
      <div className="shrink-0 w-14 pt-4 text-right">
        <span className="text-xs font-black text-slate-900 tabular-nums">{time || ""}</span>
      </div>

      <div className="flex-1 bg-white/60 backdrop-blur-md rounded-2xl border border-white/70 shadow-sm p-4 hover:shadow-md transition-shadow flex gap-4">
        {/* Thumbnail. `activity.image_url` is rendered when present; nothing populates it yet —
            venue photos need a Google Places proxy, since their terms forbid caching. Until
            then the category wash stands in. */}
        <div
          className={`relative shrink-0 w-32 h-28 md:w-56 md:h-44 rounded-xl overflow-hidden bg-gradient-to-br ${wash} flex items-center justify-center`}
        >
          {showImage ? (
            <img
              src={imageUrl}
              alt=""
              loading="lazy"
              // A dead hotlink must fall back to the wash, not leave a broken-image icon.
              onError={() => setImageFailed(true)}
              className="absolute inset-0 w-full h-full object-cover"
            />
          ) : (
            <Icon size={26} className="text-slate-700/60" />
          )}
        </div>

        <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-3 mb-2">
          <div className="min-w-0">
            <p className="text-[10px] font-black uppercase tracking-widest text-slate-400 leading-none mb-1">
              {type === "meal" ? "Meal" : activity?.category || "Stop"}
            </p>
            <h3 className="font-black text-slate-900 leading-tight">{activity?.name || label}</h3>
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
      </div>
    </article>
  )
}

export default TimelineItem
