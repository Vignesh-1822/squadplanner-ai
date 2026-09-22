import { useEffect, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { Clock, ShieldCheck, ArrowRight } from "lucide-react"
import { getTripById } from "@/services/ApiList"

const AVATAR_COLORS = [
  "bg-orange-500", "bg-pink-500", "bg-purple-600", "bg-teal-500",
  "bg-blue-600", "bg-indigo-600", "bg-rose-500", "bg-emerald-600",
]

/** Counts down to `expiresAt`, re-rendering once a second until it passes. */
function useCountdown(expiresAt) {
  const [remaining, setRemaining] = useState("")

  useEffect(() => {
    if (!expiresAt) return undefined

    const tick = () => {
      const distance = new Date(expiresAt).getTime() - Date.now()
      if (distance < 0) {
        setRemaining("Expired")
        return false
      }
      const hours = Math.floor(distance / 3600000)
      const minutes = Math.floor((distance % 3600000) / 60000)
      const seconds = Math.floor((distance % 60000) / 1000)
      setRemaining(`${hours}h ${minutes}m ${seconds}s`)
      return true
    }

    tick()
    const timer = setInterval(() => {
      if (!tick()) clearInterval(timer)
    }, 1000)
    return () => clearInterval(timer)
  }, [expiresAt])

  return remaining
}

const InvitesSent = () => {
  const { tripId } = useParams()
  const navigate = useNavigate()

  const { data: trip, isLoading } = useQuery({
    queryKey: ["trip", tripId],
    queryFn: () => getTripById(tripId),
    enabled: !!tripId,
  })

  const timeLeft = useCountdown(trip?.expires_at)

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center min-h-[60vh]">
        <div className="animate-pulse text-slate-500 font-medium">Summoning the squad...</div>
      </div>
    )
  }

  if (!trip) {
    return (
      <div className="flex-1 flex items-center justify-center min-h-[60vh] text-slate-500">
        Trip details not found.
      </div>
    )
  }

  const members = trip.invited_members || []
  const visible = members.slice(0, 3)
  const overflow = members.length - visible.length

  return (
    <main className="flex-1 flex items-center justify-center px-4 py-4 md:py-6 relative overflow-hidden h-[calc(100vh-96px)] md:h-[calc(100vh-110px)]">
      <div className="absolute -top-24 -left-24 w-64 h-64 bg-primary/10 rounded-full blur-[80px] pointer-events-none" />
      <div className="absolute -bottom-24 -right-24 w-64 h-64 bg-primary/5 rounded-full blur-[80px] pointer-events-none" />

      <div className="bg-white/70 backdrop-blur-xl max-w-2xl w-full rounded-[2rem] md:rounded-[3rem] border border-white/85 shadow-xl shadow-primary/10 p-6 md:p-12 text-center relative overflow-hidden z-10 flex flex-col items-center justify-center max-h-full overflow-y-auto md:overflow-hidden">
        <h1 className="text-3xl md:text-4xl lg:text-5xl font-black tracking-tighter mb-4 text-slate-900 leading-none">
          The Squad is{" "}
          <span className="bg-primary px-2 py-0.5 text-slate-900 inline-block transform -rotate-1 shadow-sm">
            Summoned!
          </span>
        </h1>

        <p className="text-sm md:text-base text-slate-600 mb-8 max-w-sm font-medium leading-relaxed">
          Ready to set the vibe? Your crew is waiting for your lead.
        </p>

        <div className="flex items-center justify-center -space-x-3 mb-10">
          {visible.map((member, index) => {
            const email = member.email || ""
            return (
              <div key={email || index} className="group relative">
                <div
                  className={`flex items-center justify-center h-12 w-12 rounded-full ring-4 ring-white text-white font-black text-base shadow-sm select-none ${
                    AVATAR_COLORS[index % AVATAR_COLORS.length]
                  }`}
                >
                  {email ? email[0].toUpperCase() : "?"}
                </div>
                <div className="absolute bottom-full mb-2 left-1/2 -translate-x-1/2 px-2.5 py-1 bg-slate-900 text-white text-[10px] font-bold rounded shadow-md opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-20">
                  {email}
                </div>
              </div>
            )
          })}
          {overflow > 0 && (
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 ring-4 ring-white text-slate-600 font-bold text-xs shadow-sm">
              +{overflow}
            </div>
          )}
        </div>

        <button
          type="button"
          onClick={() => navigate(`/trips/${trip.trip_id}/preferences`)}
          className="group relative flex items-center gap-3 bg-[#1e230f] hover:bg-[#2d3417] text-primary px-8 py-3.5 rounded-xl text-base font-black transition-all hover:shadow-lg hover:shadow-primary/10 hover:-translate-y-0.5 active:scale-95 duration-200"
        >
          ENTER MY PREFERENCES
          <ArrowRight size={18} className="transition-transform duration-300 group-hover:translate-x-2" />
        </button>

        <div className="mt-8 flex flex-col md:flex-row gap-6 items-center justify-center opacity-60 text-slate-600">
          <div className="flex items-center gap-2">
            <Clock size={14} className="animate-pulse text-primary-dim" />
            <span className="text-[10px] md:text-xs font-bold uppercase tracking-widest">
              Expires in {timeLeft || "24h"}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <ShieldCheck size={14} className="text-primary-dim" />
            <span className="text-[10px] md:text-xs font-bold uppercase tracking-widest">
              End-to-End Encrypted
            </span>
          </div>
        </div>
      </div>
    </main>
  )
}

export default InvitesSent
