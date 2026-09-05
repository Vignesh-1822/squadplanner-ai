import { useState, useEffect } from "react"
import { useNavigate } from "react-router-dom"
import { Plane, Umbrella, Ship, Calendar, CheckCircle2, Clock, Sparkles, Plus, Filter, Check } from "lucide-react"
import { getTrips } from "@/services/ApiList"
import { isPlanning, isComplete } from "@/lib/tripStatus"
import { useAuth } from "@/store/authStore"
import { toast } from "sonner"

const MyTrips = () => {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [trips, setTrips] = useState([])
  const [loading, setLoading] = useState(true)
  
  // Filter States
  const [filterOpen, setFilterOpen] = useState(false)
  const [selectedStatus, setSelectedStatus] = useState([])
  const [tempStatus, setTempStatus] = useState([])

  useEffect(() => {
    const fetchTrips = async () => {
      try {
        const email = user?.email || ""
        const data = await getTrips(email)
        setTrips(data)
      } catch (error) {
        console.error("Error fetching trips:", error)
        toast.error("Failed to load trips.")
      } finally {
        setLoading(false)
      }
    }

    fetchTrips()
  }, [user])

  const formatDateRange = (start, end) => {
    if (!start || !end) return "Dates TBD"
    const startDate = new Date(start)
    const endDate = new Date(end)
    const options = { month: "short", day: "numeric" }
    const startStr = startDate.toLocaleDateString("en-US", options)
    
    const endStr = startDate.getMonth() === endDate.getMonth()
      ? endDate.getDate()
      : endDate.toLocaleDateString("en-US", options)
    return `${startStr} — ${endStr}`
  }

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center min-h-[60vh]">
        <div className="animate-pulse text-slate-500 font-medium">Loading your journeys...</div>
      </div>
    )
  }  return (
    <main className="flex-1 max-w-7xl mx-auto w-full px-8 py-10 flex flex-col min-h-0 overflow-hidden space-y-6">
      {/* Hero Section */}
      <section className="space-y-4 flex-shrink-0">
        <p className="text-xs font-black uppercase tracking-[0.3em] text-slate-500 opacity-60">Active Journeys</p>
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
          <h2 className="text-5xl md:text-7xl font-black leading-none tracking-tight text-slate-900">
            Where to <span className="relative inline-block isolate">next?<span className="absolute bottom-1.5 left-0 w-full h-4 bg-primary/40 -z-10"></span></span>
          </h2>
          <div className="flex gap-3 relative">
            <button 
              onClick={() => {
                setTempStatus([...selectedStatus])
                setFilterOpen(!filterOpen)
              }}
              className="px-6 py-3 rounded-full breezy-glass hover:bg-white text-slate-800 hover:text-black transition-all flex items-center gap-2 font-bold text-sm cursor-pointer shadow-sm animate-in fade-in"
            >
              <Filter size={16} />
              Filter
            </button>
            
            {filterOpen && (
              <div className="absolute right-0 top-full mt-2 w-64 bg-white/95 backdrop-blur-md rounded-3xl p-5 border border-white/80 shadow-2xl z-50 animate-in fade-in slide-in-from-top-2 duration-200">
                <div className="text-[10px] font-black uppercase tracking-widest text-slate-400 mb-3.5">
                  FILTER BY STATUS
                </div>
                
                <div className="space-y-1">
                  {/* Assembling Option */}
                  <div 
                    onClick={() => setTempStatus((prev) => prev.includes("assembling") ? prev.filter((s) => s !== "assembling") : [...prev, "assembling"])}
                    className={`rounded-xl p-2.5 flex items-center justify-between cursor-pointer transition-all border ${
                      tempStatus.includes("assembling") 
                        ? "bg-primary/15 border-primary/20" 
                        : "border-transparent hover:bg-slate-50"
                    }`}
                  >
                    <div className="flex items-center flex-1">
                      <span className={`w-1 rounded-full transition-all ${tempStatus.includes("assembling") ? "h-5 bg-primary" : "h-4 bg-slate-100"}`} />
                      <span className={`text-sm ml-2.5 flex-1 ${tempStatus.includes("assembling") ? "font-black text-slate-900" : "font-extrabold text-slate-700"}`}>
                        Assembling
                      </span>
                    </div>
                    <div className={`w-4.5 h-4.5 rounded-full border flex items-center justify-center flex-shrink-0 transition-all ${
                      tempStatus.includes("assembling") ? "bg-primary border-primary text-slate-900" : "border-slate-200"
                    }`}>
                      {tempStatus.includes("assembling") && <Check size={10} strokeWidth={3} />}
                    </div>
                  </div>

                  {/* Synced Option */}
                  <div 
                    onClick={() => setTempStatus((prev) => prev.includes("synced") ? prev.filter((s) => s !== "synced") : [...prev, "synced"])}
                    className={`rounded-xl p-2.5 flex items-center justify-between cursor-pointer transition-all border ${
                      tempStatus.includes("synced") 
                        ? "bg-primary/15 border-primary/20" 
                        : "border-transparent hover:bg-slate-50"
                    }`}
                  >
                    <div className="flex items-center flex-1">
                      <span className={`w-1.5 rounded-full transition-all ${tempStatus.includes("synced") ? "h-5 bg-primary" : "h-4 bg-slate-100"}`} />
                      <span className={`text-sm ml-2.5 flex-1 ${tempStatus.includes("synced") ? "font-black text-slate-900" : "font-extrabold text-slate-700"}`}>
                        Synced
                      </span>
                    </div>
                    <div className={`w-4.5 h-4.5 rounded-full border flex items-center justify-center flex-shrink-0 transition-all ${
                      tempStatus.includes("synced") ? "bg-primary border-primary text-slate-900" : "border-slate-200"
                    }`}>
                      {tempStatus.includes("synced") && <Check size={10} strokeWidth={3} />}
                    </div>
                  </div>

                  {/* Finalized Option */}
                  <div 
                    onClick={() => setTempStatus((prev) => prev.includes("finalized") ? prev.filter((s) => s !== "finalized") : [...prev, "finalized"])}
                    className={`rounded-xl p-2.5 flex items-center justify-between cursor-pointer transition-all border ${
                      tempStatus.includes("finalized") 
                        ? "bg-primary/15 border-primary/20" 
                        : "border-transparent hover:bg-slate-50"
                    }`}
                  >
                    <div className="flex items-center flex-1">
                      <span className={`w-1 rounded-full transition-all ${tempStatus.includes("finalized") ? "h-5 bg-primary" : "h-4 bg-slate-100"}`} />
                      <span className={`text-sm ml-2.5 flex-1 ${tempStatus.includes("finalized") ? "font-black text-slate-900" : "font-extrabold text-slate-700"}`}>
                        Finalized
                      </span>
                    </div>
                    <div className={`w-4.5 h-4.5 rounded-full border flex items-center justify-center flex-shrink-0 transition-all ${
                      tempStatus.includes("finalized") ? "bg-primary border-primary text-slate-900" : "border-slate-200"
                    }`}>
                      {tempStatus.includes("finalized") && <Check size={10} strokeWidth={3} />}
                    </div>
                  </div>

                  {/* Cancelled Option */}
                  <div 
                    onClick={() => setTempStatus((prev) => prev.includes("cancelled") ? prev.filter((s) => s !== "cancelled") : [...prev, "cancelled"])}
                    className={`rounded-xl p-2.5 flex items-center justify-between cursor-pointer transition-all border ${
                      tempStatus.includes("cancelled") 
                        ? "bg-primary/15 border-primary/20" 
                        : "border-transparent hover:bg-slate-50"
                    }`}
                  >
                    <div className="flex items-center flex-1">
                      <span className={`w-1 rounded-full transition-all ${tempStatus.includes("cancelled") ? "h-5 bg-primary" : "h-4 bg-slate-100"}`} />
                      <span className={`text-sm ml-2.5 flex-1 ${tempStatus.includes("cancelled") ? "font-black text-slate-900" : "font-extrabold text-slate-700"}`}>
                        Cancelled
                      </span>
                    </div>
                    <div className={`w-4.5 h-4.5 rounded-full border flex items-center justify-center flex-shrink-0 transition-all ${
                      tempStatus.includes("cancelled") ? "bg-primary border-primary text-slate-900" : "border-slate-200"
                    }`}>
                      {tempStatus.includes("cancelled") && <Check size={10} strokeWidth={3} />}
                    </div>
                  </div>
                </div>

                {/* Divider */}
                <div className="border-t border-slate-100 my-3.5" />

                {/* Action Buttons */}
                <div className="flex justify-between items-center">
                  <button 
                    onClick={() => setTempStatus([])}
                    className="text-slate-400 hover:text-slate-900 font-black text-[11px] uppercase tracking-wider transition-colors cursor-pointer"
                  >
                    RESET
                  </button>
                  <button 
                    onClick={() => {
                      setSelectedStatus(tempStatus)
                      setFilterOpen(false)
                    }}
                    className="bg-slate-950 hover:bg-slate-900 text-primary font-black px-6 py-2.5 rounded-full text-[11px] uppercase tracking-widest shadow-md transition-all active:scale-95 cursor-pointer"
                  >
                    APPLY
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* Clean Minimal Grid Area (only this scrolls internally if cards overflow) */}
      <div className="flex-1 overflow-y-auto min-h-0 pr-1 py-2 custom-scroll">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {trips.filter((trip) => {
            if (selectedStatus.length === 0) return true
            const isReady = isComplete(trip.status)
            const isSynced = isPlanning(trip.status)
            const isAssembling = !isReady && !isSynced

            if (selectedStatus.includes("assembling") && isAssembling) return true
            if (selectedStatus.includes("synced") && isSynced) return true
            if (selectedStatus.includes("finalized") && isReady) return true
            if (selectedStatus.includes("cancelled") && trip.status === "cancelled") return true
            return false
          }).map((trip) => {
            // Backend trip status: pending -> collecting -> generating -> city_selection -> complete
            const isReady = isComplete(trip.status)
            const isSynced = isPlanning(trip.status)
            const isAssembling = !isReady && !isSynced

            // Custom styling for card header icons and badges mapping Stitch colors
            let badgeBg = "bg-slate-100 text-slate-900"
            let badgeText = "Assembling"
            let badgeIcon = <Clock size={14} className="animate-pulse text-primary" />
            let tripIcon = <Umbrella className="text-slate-400" size={24} />

            if (isReady) {
              badgeBg = "bg-primary text-on-primary volt-glow"
              badgeText = "Ready to Fly"
              badgeIcon = <CheckCircle2 size={14} />
              tripIcon = <Plane className="text-slate-400" size={24} />
            } else if (isSynced) {
              badgeBg = "bg-teal-50 text-teal-600"
              badgeText = "Planning"
              badgeIcon = <Sparkles size={14} />
              tripIcon = <Ship className="text-slate-400" size={24} />
            }

            const members = trip.invited_members || []
            const displayedMembers = members.slice(0, 2)
            const remainingCount = members.length - displayedMembers.length

            return (
              <div
                key={trip.trip_id}
                className="breezy-glass rounded-[2rem] p-8 flex flex-col justify-between hover-lift relative group min-h-[320px]"
              >
                <div className="space-y-8">
                  <div className="flex justify-between items-center">
                    <span className={`${badgeBg} text-[10px] font-black uppercase tracking-widest px-4 py-1.5 rounded-full flex items-center gap-1.5`}>
                      {badgeIcon}
                      {badgeText}
                    </span>
                    {tripIcon}
                  </div>
                  <div>
                    <h3 className="text-3xl font-black text-slate-900 leading-tight truncate">{trip.trip_name}</h3>
                    <p className="text-slate-500 font-medium mt-3 text-sm line-clamp-2">
                      {trip.selected_destination
                        ? `Adventure to ${trip.selected_destination.city || trip.selected_destination.name || "selected destination"}. AI curated itineraries and flight details ready.`
                        : "Waiting for the squad to finalize budgets, dates, and sync preferences."}
                    </p>
                  </div>
                  <div className="flex items-center gap-4 py-4 border-y border-slate-100/50">
                    <div className="flex items-center gap-2 text-xs font-bold text-slate-600 uppercase tracking-widest">
                      <Calendar size={16} className="text-primary" />
                      {formatDateRange(trip.start_date, trip.end_date)}
                    </div>
                  </div>
                </div>

                <div className="mt-8 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="flex -space-x-2">
                      {displayedMembers.map((member, idx) => {
                        const email = member.email || ""
                        const initial = email ? email[0].toUpperCase() : "?"
                        const bgColors = ["bg-orange-500", "bg-pink-500", "bg-purple-600"]
                        return (
                          <div
                            key={idx}
                            className={`w-8 h-8 rounded-full border-2 border-white flex items-center justify-center text-[10px] font-bold text-white shadow-sm ${bgColors[idx % bgColors.length]}`}
                          >
                            {initial}
                          </div>
                        )
                      })}
                    </div>
                    {remainingCount > 0 && (
                      <span className="text-[10px] font-black text-slate-400 tracking-tighter uppercase">
                        +{remainingCount} Members
                      </span>
                    )}
                  </div>
                  
                  <button
                    onClick={() => navigate(`/trips/${trip.trip_id}/lobby`)}
                    className={`${
                      isAssembling
                        ? "bg-primary text-slate-900 volt-glow hover:scale-105"
                        : "bg-slate-900 text-primary hover:scale-105"
                    } px-6 py-3 rounded-full font-black text-[10px] uppercase tracking-widest active:scale-95 transition-all cursor-pointer`}
                  >
                    {isReady ? "Details" : isAssembling ? "Join Plan" : "Manage"}
                  </button>
                </div>
              </div>
            )
          })}

          {/* Add New Placeholder Card */}
          <div
            onClick={() => navigate("/trips/new")}
            className="border-2 border-dashed border-primary/40 rounded-[2rem] p-12 flex flex-col items-center justify-center text-center space-y-6 hover:bg-primary/5 transition-all group cursor-pointer"
          >
            <div className="w-16 h-16 bg-primary/20 text-primary rounded-full flex items-center justify-center group-hover:scale-110 transition-transform shadow-sm">
              <Plus size={32} strokeWidth={3} />
            </div>
            <div>
              <h4 className="font-black text-xl tracking-tight text-slate-900">No more plans?</h4>
              <p className="text-slate-400 font-medium mt-1 text-xs">Conquer the map with your squad.</p>
            </div>
            <button className="bg-slate-900 text-primary font-black px-8 py-3 rounded-full transition-all text-[10px] uppercase tracking-widest group-hover:scale-105 active:scale-95 cursor-pointer">
              New Journey
            </button>
          </div>
        </div>
      </div>

      {/* Minimal Footer */}
      <footer className="max-w-7xl mx-auto w-full py-4 border-t border-slate-100 flex flex-col md:flex-row justify-between items-center gap-8 text-slate-400 text-[10px] font-black uppercase tracking-widest flex-shrink-0">
        <div className="flex items-center gap-4">
          <div className="w-8 h-8 bg-slate-50 flex items-center justify-center rounded-lg border border-slate-100">
            <Plane className="text-primary" size={16} />
          </div>
          <p>© 2026 SquadPlanner</p>
        </div>
        <div className="flex gap-8">
          <a className="hover:text-primary transition-colors" href="#">Privacy</a>
          <a className="hover:text-primary transition-colors" href="#">Terms</a>
          <a className="hover:text-primary transition-colors" href="#">Support</a>
        </div>
      </footer>
    </main>
  )
}

export default MyTrips
