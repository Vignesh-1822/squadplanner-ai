import { Flag, ChevronRight } from "lucide-react"
import { useNavigate, useParams } from "react-router-dom"

const AVATAR_COLORS = [
  "bg-amber-500",
  "bg-[#ff71cf]",
  "bg-purple-600",
  "bg-teal-500",
  "bg-blue-600",
]

/**
 * Stitch Next Up widget:
 * Solid Electric Volt card, floating white milestone card with pink accent dot,
 * squad avatars, interactive itinerary link, and squad cheer slogan.
 */
const NextUpWidget = ({ itinerary }) => {
  const navigate = useNavigate()
  const { tripId } = useParams()
  const members = itinerary?.members || []
  const hotel = itinerary?.hotel
  const days = itinerary?.days || []
  const dayOne = days[0]
  const dayOneDinner = dayOne?.meals?.[dayOne.meals.length - 1] || "Day 1 Dinner"

  const displayedMembers = members.slice(0, 3)
  const remainingCount = members.length - displayedMembers.length

  return (
    <section className="bg-primary rounded-3xl p-6 relative overflow-hidden shadow-xl shadow-primary/25 text-slate-900 flex flex-col justify-between min-h-[380px]">
      {/* Ambient background glow from Stitch */}
      <div className="absolute -top-6 -right-6 size-24 bg-white/30 rounded-full blur-2xl pointer-events-none" />

      <div>
        <header className="flex items-center gap-2 mb-5">
          <Flag size={20} className="text-slate-900 fill-slate-900" />
          <h2 className="font-black text-xl text-slate-900 tracking-tight">Next Up</h2>
        </header>

        {/* Floating Milestone Card */}
        <div className="bg-white/90 backdrop-blur-sm p-5 rounded-2xl mb-4 shadow-sm relative text-slate-900">
          <div className="absolute -left-1.5 top-4 size-3 bg-[#ff71cf] rounded-full border-2 border-white shadow-sm" />
          <p className="font-black text-slate-900 leading-tight text-base">
            {hotel ? "Lodging Confirmed" : "Book Flights by Friday"}
          </p>
          <p className="text-xs text-slate-600 font-medium mt-1 line-clamp-2">
            {hotel
              ? `${hotel.name} — ${hotel.address || "Downtown base"}`
              : `${members.length} squad members ready to coordinate tickets.`}
          </p>

          <div className="mt-4 flex -space-x-2 items-center">
            {displayedMembers.map((member, i) => (
              <div
                key={member.member_id || i}
                title={member.name}
                className={`size-7 rounded-full border-2 border-white text-white text-[10px] font-black flex items-center justify-center shadow-sm ${
                  AVATAR_COLORS[i % AVATAR_COLORS.length]
                }`}
              >
                {(member.name || "?")[0].toUpperCase()}
              </div>
            ))}
            {remainingCount > 0 && (
              <div className="size-7 rounded-full border-2 border-white bg-slate-900 text-primary text-[10px] font-black flex items-center justify-center shadow-sm">
                +{remainingCount}
              </div>
            )}
          </div>
        </div>

        {/* Interactive Itinerary Preview Link */}
        <button
          type="button"
          onClick={() => navigate(`/trips/${tripId}/hub/itinerary`)}
          className="w-full bg-white/40 hover:bg-white/70 active:scale-[0.98] transition-all p-3.5 rounded-2xl flex items-center justify-between border border-white/30 text-slate-900 cursor-pointer text-left group"
        >
          <p className="text-xs font-black italic truncate pr-2">
            Vote on {dayOneDinner}
          </p>
          <ChevronRight
            size={16}
            strokeWidth={3}
            className="text-slate-900 shrink-0 transform group-hover:translate-x-1 transition-transform"
          />
        </button>
      </div>

      {/* Hand-drawn style slogan from Stitch */}
      <div className="mt-4 text-slate-900/70 font-black text-[10px] uppercase text-center tracking-wider select-none">
        Keep pushing, Squad! 🚀
      </div>
    </section>
  )
}

export default NextUpWidget
