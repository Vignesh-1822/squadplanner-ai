import { Users, Check, Plus } from "lucide-react"
import { formatMoney } from "@/lib/itinerary"
import { toast } from "sonner"

const AVATAR_COLORS = [
  "bg-amber-500",
  "bg-[#ff71cf]",
  "bg-purple-600",
  "bg-teal-500",
  "bg-blue-600",
  "bg-rose-500",
  "bg-emerald-500",
]

/**
 * Stitch Squad widget:
 * Rounded-3xl glass card, 'X/Y Ready' pink badge, rounded-square avatars with volt rings,
 * green check badges, confirmed pill badges, and dashed invite button.
 */
const SquadPanel = ({ members = [], flights = [] }) => {
  const flightFor = (memberId) => flights?.find((flight) => flight.member_id === memberId)

  const handleInvite = () => {
    navigator.clipboard.writeText(window.location.href)
    toast.success("Trip invite link copied to clipboard!")
  }

  return (
    <section className="bg-white/60 backdrop-blur-xl rounded-3xl border border-white/70 shadow-sm p-6 relative overflow-hidden flex flex-col justify-between min-h-[380px]">
      <div>
        <header className="flex items-center justify-between gap-3 mb-6">
          <h2 className="flex items-center gap-2.5 text-xl font-black text-slate-900 tracking-tight">
            <Users size={22} className="text-primary fill-primary" />
            The Squad
          </h2>
          <span className="text-xs font-black text-[#ff71cf] bg-[#ff71cf]/10 px-2.5 py-1 rounded-full uppercase tracking-tight italic">
            {members.length}/{members.length} Ready
          </span>
        </header>

        <ul className="space-y-4">
          {members.map((member, index) => {
            const flight = flightFor(member.member_id)
            return (
              <li
                key={member.member_id || index}
                className="flex items-center justify-between gap-3 group"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <div className="relative shrink-0">
                    <span
                      className={`size-12 rounded-2xl flex items-center justify-center text-white font-black text-base ring-2 ring-primary shadow-sm ${
                        AVATAR_COLORS[index % AVATAR_COLORS.length]
                      }`}
                    >
                      {(member.name || "?")[0].toUpperCase()}
                    </span>
                    <span className="absolute -bottom-1 -right-1 bg-primary text-slate-900 rounded-full size-5 flex items-center justify-center border-2 border-white shadow-sm">
                      <Check size={11} strokeWidth={3.5} />
                    </span>
                  </div>

                  <div className="min-w-0">
                    <p className="font-bold text-slate-900 text-sm truncate">
                      {member.name}
                      {member.is_leader && (
                        <span className="text-xs font-semibold text-slate-500 ml-1">
                          (Organizer)
                        </span>
                      )}
                    </p>
                    <p className="text-xs text-slate-500 font-medium truncate">
                      {member.is_leader ? "Host" : "Trip Enthusiast"}
                      {member.origin_city && ` · ${member.origin_city}`}
                    </p>
                  </div>
                </div>

                <div className="text-right shrink-0">
                  <span className="inline-block text-[10px] font-black text-green-700 bg-green-100 px-2.5 py-1 rounded-full uppercase tracking-wider">
                    CONFIRMED
                  </span>
                  {flight && (
                    <p className="text-[10px] font-bold text-slate-400 mt-0.5">
                      {formatMoney(flight.price_usd)}
                    </p>
                  )}
                </div>
              </li>
            )
          })}
        </ul>
      </div>

      <button
        type="button"
        onClick={handleInvite}
        className="w-full mt-6 py-3 border-2 border-dashed border-slate-300 hover:border-primary hover:bg-primary/5 rounded-2xl text-slate-500 hover:text-slate-900 transition-all font-black text-xs uppercase tracking-wider flex items-center justify-center gap-1.5 cursor-pointer"
      >
        <Plus size={15} strokeWidth={2.5} />
        Invite more friends
      </button>
    </section>
  )
}

export default SquadPanel
