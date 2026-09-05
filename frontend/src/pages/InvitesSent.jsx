import { useState, useEffect } from "react"
import { useNavigate } from "react-router-dom"
import { Clock, ShieldCheck, ArrowRight } from "lucide-react"
import { getTripById } from "@/services/ApiList"

const InvitesSent = () => {
  const navigate = useNavigate()
  const [trip, setTrip] = useState(null)
  const [timeLeft, setTimeLeft] = useState("")
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const tripId = sessionStorage.getItem("currentTripId")
    if (!tripId) {
      navigate("/trips/new")
      return
    }

    let timer
    const fetchTrip = async () => {
      try {
        const data = await getTripById(tripId)
        setTrip(data)
        if (data.expires_at) {
          timer = startCountdown(data.expires_at)
        }
      } catch (error) {
        console.error("Error fetching trip:", error)
      } finally {
        setLoading(false)
      }
    }

    fetchTrip()
    return () => { if (timer) clearInterval(timer) }
  }, [navigate])

  const startCountdown = (expiryDate) => {
    const update = () => {
      const distance = new Date(expiryDate).getTime() - Date.now()
      if (distance < 0) {
        setTimeLeft("Expired")
        return false
      }
      const hours = Math.floor(distance / (1000 * 60 * 60))
      const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60))
      const seconds = Math.floor((distance % (1000 * 60)) / 1000)
      setTimeLeft(`${hours}h ${minutes}m ${seconds}s`)
      return true
    }
    update()
    const timer = setInterval(() => { if (!update()) clearInterval(timer) }, 1000)
    return timer
  }

  if (loading) return (
    <div className="flex-1 flex items-center justify-center min-h-[60vh]">
      <div className="animate-pulse text-slate-500 font-medium">Summoning the squad...</div>
    </div>
  )

  if (!trip) return (
    <div className="flex-1 flex items-center justify-center min-h-[60vh] text-slate-500">
      Trip details not found.
    </div>
  )

  const members = trip.invited_members || []
  const maxAvatars = 3
  const visibleMembers = members.slice(0, maxAvatars)
  const overflowCount = members.length - maxAvatars

  return (
    <main className="flex-1 flex items-center justify-center px-4 py-4 md:py-6 relative overflow-hidden h-[calc(100vh-96px)] md:h-[calc(100vh-110px)]">
      {/* Background Ambient Glows */}
      <div className="absolute -top-24 -left-24 w-64 h-64 bg-[#d1f94d]/10 rounded-full blur-[80px] pointer-events-none"></div>
      <div className="absolute -bottom-24 -right-24 w-64 h-64 bg-[#d1f94d]/5 rounded-full blur-[80px] pointer-events-none"></div>

      {/* Main Success Card (Forced Light-Theme to match Stitch design exactly) */}
      <div className="bg-white/70 backdrop-blur-xl max-w-2xl w-full rounded-[2rem] md:rounded-[3rem] border border-white/85 shadow-xl shadow-[#d1f94d]/10 p-6 md:p-12 text-center relative overflow-hidden z-10 flex flex-col items-center justify-center max-h-full overflow-y-auto md:overflow-hidden">
        {/* Headline */}
        <h1 className="text-3xl md:text-4xl lg:text-5xl font-black tracking-tighter mb-4 text-slate-900 leading-none">
          The Squad is <span className="bg-[#d1f94d] px-2 py-0.5 text-slate-900 inline-block transform -rotate-1 shadow-sm">Summoned!</span>
        </h1>
        
        <p className="text-sm md:text-base text-slate-600 mb-8 max-w-sm font-medium leading-relaxed">
          Ready to set the vibe? Your crew is waiting for your lead.
        </p>

        {/* Overlapping Avatar Stack */}
        <div className="flex items-center justify-center -space-x-3 mb-10">
          {visibleMembers.map((member, idx) => {
            const email = member.email || ""
            const firstLetter = email ? email[0].toUpperCase() : "?"
            const bgColors = [
              "bg-orange-500",
              "bg-pink-500",
              "bg-purple-600",
              "bg-teal-500",
              "bg-blue-600",
              "bg-indigo-600",
              "bg-rose-500",
              "bg-emerald-600"
            ]
            const bgColor = bgColors[idx % bgColors.length]
            return (
              <div key={idx} className="group relative">
                <div className={`flex items-center justify-center h-12 w-12 rounded-full ring-4 ring-white text-white font-black text-base shadow-sm ${bgColor} hover:scale-105 active:scale-95 transition-all cursor-default select-none`}>
                  {firstLetter}
                </div>
                <div className="absolute bottom-full mb-2 left-1/2 -translate-x-1/2 px-2.5 py-1 bg-slate-900 text-white text-[10px] font-bold rounded shadow-md opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-20">
                  {email}
                </div>
              </div>
            )
          })}
          {overflowCount > 0 && (
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 ring-4 ring-white text-slate-600 font-bold text-xs shadow-sm">
              +{overflowCount}
            </div>
          )}
        </div>

        {/* CTA Button */}
        <button
          onClick={() => navigate(`/trips/${trip.trip_id}/preferences`)}
          className="group relative flex items-center gap-3 bg-[#1e230f] hover:bg-[#2d3417] text-[#d1f94d] px-8 py-3.5 rounded-xl text-base font-black transition-all hover:shadow-lg hover:shadow-[#d1f94d]/10 hover:-translate-y-0.5 active:scale-95 duration-200"
        >
          ENTER MY PREFERENCES
          <ArrowRight size={18} className="transition-transform duration-300 group-hover:translate-x-2" />
        </button>

        {/* Secondary Info */}
        <div className="mt-8 flex flex-col md:flex-row gap-6 items-center justify-center opacity-60 text-slate-600">
          <div className="flex items-center gap-2">
            <Clock size={14} className="animate-pulse text-[#afd528]" />
            <span className="text-[10px] md:text-xs font-bold uppercase tracking-widest">Expires in {timeLeft || "24h"}</span>
          </div>
          <div className="flex items-center gap-2">
            <ShieldCheck size={14} className="text-[#afd528]" />
            <span className="text-[10px] md:text-xs font-bold uppercase tracking-widest">End-to-End Encrypted</span>
          </div>
        </div>
      </div>
    </main>
  )
}

export default InvitesSent
