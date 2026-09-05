import { useParams, useNavigate } from "react-router-dom"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Users, Mail, Copy, PlusCircle, Check, RefreshCw, CheckCircle2, Shield, X, Sparkles } from "lucide-react"
import { getTripById, generateTrip, removeMember } from "@/services/ApiList"
import { useAuth } from "@/store/authStore"
import { isPlanning, isComplete, lobbyRefetchInterval, MEMBER_READY, MEMBER_JOINED } from "@/lib/tripStatus"
import { toast } from "sonner"

const AVATAR_COLORS = ["bg-orange-500", "bg-pink-500", "bg-purple-600", "bg-teal-500", "bg-blue-600"]

const TripLobby = () => {
  const { tripId } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const queryClient = useQueryClient()

  const { data: trip, isLoading } = useQuery({
    queryKey: ["trip", tripId],
    queryFn: () => getTripById(tripId),
    enabled: !!tripId,
    // Refetches on window focus by default, and pauses while the tab is hidden — which is
    // where a lobby spends most of its life.
    refetchInterval: (query) => lobbyRefetchInterval(query.state.data),
  })

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["trip", tripId] })

  const { mutate: startPlanning, isPending: isStarting } = useMutation({
    mutationFn: () => generateTrip(tripId),
    onSuccess: () => {
      toast.success("Scouting destinations for your squad...")
      invalidate()
    },
    // 403 (not the leader), 409 (already started), 422 (someone hasn't submitted, no
    // overlapping dates, too many members) — all written for users, so show them as-is.
    onError: (error) => toast.error(error.message),
  })

  const { mutate: dropMember } = useMutation({
    mutationFn: (email) => removeMember(tripId, email),
    onSuccess: (_data, email) => {
      toast.success(`${email} removed from the squad.`)
      invalidate()
    },
    onError: (error) => toast.error(error.message),
  })

  const handleCopyLink = () => {
    navigator.clipboard.writeText(`${window.location.origin}/join/${trip?.invite_code || ""}`)
    toast.success("Invite link copied to clipboard!")
  }

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center min-h-[60vh]">
        <div className="animate-pulse text-slate-500 font-medium">Entering the lobby...</div>
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

  // TODO(F3): route to /trips/:tripId/planning and /trips/:tripId/itinerary once those exist.
  // Until then the lobby reports the run in place rather than sending anyone to a blank page.
  if (isPlanning(trip.status) || isComplete(trip.status)) {
    const done = isComplete(trip.status)
    return (
      <main className="flex-1 flex items-center justify-center px-6 min-h-[60vh]">
        <div className="bg-white/50 backdrop-blur-md rounded-[2rem] border border-white/70 shadow-sm p-12 text-center max-w-lg">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/20 text-slate-800 text-[10px] font-black uppercase tracking-widest mb-5">
            {done ? <CheckCircle2 size={12} /> : <RefreshCw size={12} className="animate-spin" />}
            {done ? "Trip ready" : "Planning in progress"}
          </div>
          <h1 className="text-3xl font-black text-slate-900 tracking-tight mb-3">{trip.trip_name}</h1>
          <p className="text-slate-500 text-sm font-medium">
            {done
              ? "Your itinerary is ready. The itinerary screen lands next."
              : "The agent is scoring destinations and building your itinerary. The live planning screen lands next."}
          </p>
        </div>
      </main>
    )
  }

  const members = trip.invited_members || []
  const me = members.find((m) => m.email === user?.email)
  const isLeader = !!me?.is_leader
  const waitingOn = members.filter((m) => m.status !== MEMBER_READY)
  const waitingNames = waitingOn.map((m) => (m.email === user?.email ? "you" : m.name || m.email))
  const readiness = trip.total_count ? Math.round((trip.ready_count / trip.total_count) * 100) : 0

  return (
    <main className="flex-1 max-w-6xl mx-auto w-full px-6 py-6 lg:px-12 overflow-y-auto">
      {/* Hero Header Section */}
      <div className="flex items-center justify-between gap-4 mb-8">
        <div className="space-y-1">
          <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-primary/20 text-slate-800 text-[10px] font-bold uppercase tracking-wider">
            <span className="relative flex h-1.5 w-1.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
              <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-primary"></span>
            </span>
            Live Lobby
          </div>
          <h1 className="text-2xl md:text-3xl font-black text-slate-900 tracking-tight leading-none">
            Trip Lobby: <span className="text-primary bg-slate-900 px-3 py-1 rounded-xl inline-block ml-1 not-italic font-black text-xl md:text-2xl">{trip.trip_name}</span>
          </h1>
          <p className="text-slate-500 text-xs font-medium">Waiting for the squad to sync their vibes...</p>
        </div>

        <div className="flex items-center">
          <button
            onClick={handleCopyLink}
            className="flex items-center justify-center gap-2 px-5 h-10 bg-primary text-black rounded-xl text-xs font-bold hover:brightness-105 transition-all shadow-md shadow-primary/20 hover:scale-102 active:scale-98 cursor-pointer"
          >
            <Copy size={14} />
            Copy Invite Link
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Content: The Squad */}
        <div className="lg:col-span-2 space-y-4">
          <section className="bg-white/40 backdrop-blur-md rounded-2xl border border-white/60 p-6 shadow-sm">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-black text-slate-900 flex items-center gap-2">
                <Users className="text-primary" size={20} />
                The Squad
              </h2>
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                {trip.ready_count} of {trip.total_count} ready
              </span>
            </div>

            <div className="space-y-3">
              {members.map((member, idx) => {
                const isReady = member.status === MEMBER_READY
                const isJoined = member.status === MEMBER_JOINED
                const email = member.email || ""
                const isMe = !!user?.email && email === user.email
                const initial = email ? email[0].toUpperCase() : "?"
                const avatarBg = AVATAR_COLORS[idx % AVATAR_COLORS.length]

                return (
                  <div key={email || idx} className="flex items-center justify-between p-3.5 rounded-xl bg-white/50 border border-slate-100/50 shadow-sm transition-all hover:bg-white/60">
                    <div className="flex items-center gap-3">
                      <div className="relative">
                        {member.avatar_url ? (
                          <img
                            className={`size-10 rounded-full object-cover ring-2 ${isReady ? "ring-primary" : "ring-transparent"}`}
                            src={member.avatar_url}
                            alt={member.name}
                          />
                        ) : (
                          <div className={`size-10 rounded-full flex items-center justify-center text-white font-black text-sm shadow-sm ${avatarBg} ring-2 ${isReady ? "ring-primary" : "ring-transparent"}`}>
                            {initial}
                          </div>
                        )}
                        <span className={`absolute bottom-0 right-0 size-3 rounded-full border border-white ${isReady ? "bg-green-500" : isJoined ? "bg-amber-400" : "bg-slate-300"}`}></span>
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <h3 className="font-bold text-slate-900 text-sm leading-tight">
                            {member.name || email}
                            {isMe && <span className="text-slate-400 font-medium"> (You)</span>}
                          </h3>
                          {member.is_leader && (
                            <span className="px-2 py-0.5 rounded-full bg-slate-900 text-primary text-[9px] font-black uppercase tracking-widest">
                              Leader
                            </span>
                          )}
                        </div>
                        <p className="text-[10px] text-slate-500 font-medium mt-0.5">
                          {member.is_leader
                            ? "Vibe Master (Host)"
                            : isReady
                              ? "Ready to Roll"
                              : isJoined
                                ? "Syncing Preferences..."
                                : "Invitation Sent"}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      {isReady ? (
                        <div className="flex items-center gap-1 px-3 py-1 rounded-full bg-primary/20 text-slate-800 text-[10px] font-bold uppercase tracking-wider">
                          <CheckCircle2 size={12} className="text-green-600" />
                          READY
                        </div>
                      ) : isJoined ? (
                        <div className="flex items-center gap-1 px-3 py-1 rounded-full bg-amber-100 text-amber-700 text-[10px] font-bold uppercase tracking-wider">
                          <RefreshCw size={12} className="animate-spin" />
                          SYNCING
                        </div>
                      ) : (
                        <div className="flex items-center gap-1 px-3 py-1 rounded-full bg-slate-100 text-slate-500 text-[10px] font-bold uppercase tracking-wider">
                          <Mail size={12} />
                          PENDING
                        </div>
                      )}

                      {/* Readiness is strict, so the leader needs a way to drop a straggler. */}
                      {isLeader && !member.is_leader && (
                        <button
                          type="button"
                          onClick={() => dropMember(email)}
                          title={`Remove ${email} from the squad`}
                          className="p-1.5 rounded-full text-slate-300 hover:text-red-500 hover:bg-red-50 transition-colors cursor-pointer"
                        >
                          <X size={14} />
                        </button>
                      )}
                    </div>
                  </div>
                )
              })}

              {/* Invite more friends slot */}
              <button
                onClick={handleCopyLink}
                className="w-full flex items-center justify-center p-3 border border-dashed border-slate-200 hover:border-primary hover:bg-primary/5 rounded-xl transition-all group cursor-pointer"
              >
                <div className="flex items-center gap-2 text-slate-400 group-hover:text-primary transition-colors">
                  <PlusCircle size={16} />
                  <span className="font-bold text-xs uppercase tracking-wider">Invite more friends</span>
                </div>
              </button>
            </div>
          </section>
        </div>

        {/* Sidebar Content */}
        <div className="space-y-4">
          {/* Your own preferences — the lobby should never leave you wondering what to do next */}
          {me && me.status !== MEMBER_READY && (
            <section className="bg-white/60 backdrop-blur-md rounded-2xl border-2 border-primary/60 p-6 shadow-sm">
              <h2 className="text-sm font-black text-slate-900 mb-2 flex items-center gap-2 uppercase tracking-wider">
                <Sparkles size={16} className="text-primary" />
                Your turn
              </h2>
              <p className="text-slate-500 text-xs font-medium mb-4 leading-relaxed">
                The squad is waiting on you. Add your airport, budget, dates and travel vibes to get counted.
              </p>
              <button
                type="button"
                onClick={() => navigate(`/trips/${tripId}/preferences`)}
                className="w-full bg-slate-900 text-primary font-black text-xs uppercase tracking-widest px-6 py-3 rounded-xl transition-all hover:scale-[1.02] active:scale-95 cursor-pointer"
              >
                Add my preferences
              </button>
            </section>
          )}

          {/* Progress Card */}
          <section className="bg-slate-900 rounded-2xl p-6 text-white volt-glow">
            <h2 className="text-sm font-bold mb-4 flex items-center gap-2 text-primary uppercase tracking-wider">
              <CheckCircle2 size={16} />
              Sync Progress
            </h2>
            <div className="space-y-4">
              <div className="flex justify-between text-xs font-bold uppercase tracking-wider">
                <span>Squad Readiness</span>
                <span className="text-primary">{readiness}%</span>
              </div>
              <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
                <div className="bg-primary h-full rounded-full transition-all duration-500" style={{ width: `${readiness}%` }}></div>
              </div>

              {isLeader ? (
                <>
                  <button
                    type="button"
                    onClick={() => startPlanning()}
                    disabled={!trip.can_generate || isStarting}
                    className="w-full flex items-center justify-center gap-2 bg-primary text-slate-900 font-black text-xs uppercase tracking-widest px-6 py-3.5 rounded-xl transition-all hover:scale-[1.02] active:scale-95 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:scale-100"
                  >
                    <Sparkles size={14} />
                    {isStarting ? "Starting..." : "Scout Destinations"}
                  </button>
                  {/* A greyed-out button with no explanation is the worst version of this. */}
                  <p className="text-slate-400 text-xs leading-relaxed font-medium">
                    {trip.can_generate
                      ? "Everyone's in. Kick it off whenever you're ready."
                      : `Waiting on ${waitingOn.length} of ${trip.total_count}: ${waitingNames.join(", ")}`}
                  </p>
                </>
              ) : (
                <p className="text-slate-400 text-xs leading-relaxed font-medium">
                  {trip.can_generate
                    ? "Everyone's in. Your Vibe Master will kick things off shortly."
                    : `Waiting on ${waitingOn.length} of ${trip.total_count} to submit their preferences.`}
                </p>
              )}
            </div>
          </section>

          {/* What's Next Card */}
          {/* <section className="bg-white/40 backdrop-blur-md rounded-2xl border border-white/60 p-6 shadow-sm">
            <h2 className="text-sm font-bold text-slate-900 mb-4 uppercase tracking-wider">What&apos;s Next</h2>
            <div className="space-y-4 relative before:absolute before:left-3 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-200">

              <div className="relative pl-9">
                <div className="absolute left-0 top-0.5 size-6 rounded-full bg-primary flex items-center justify-center text-slate-900 shadow-sm">
                  <Check size={14} className="font-bold" />
                </div>
                <h4 className="font-extrabold text-slate-900 text-sm leading-none mb-1">Squad formation</h4>
                <p className="text-[13px] text-slate-500 font-medium">Invite your travel buddies to the hub.</p>
              </div>

              <div className={`relative pl-9 ${trip.all_ready ? "" : ""}`}>
                <div className={`absolute left-0 top-0.5 size-6 rounded-full flex items-center justify-center shadow-sm ${trip.all_ready ? "bg-primary text-slate-900" : "bg-primary/20 text-primary border border-primary animate-pulse"}`}>
                  {trip.all_ready ? <Check size={14} /> : <RefreshCw size={12} className="animate-spin" />}
                </div>
                <h4 className="font-extrabold text-slate-900 text-sm leading-none mb-1">Syncing vibes</h4>
                <p className="text-[13px] text-slate-500 font-medium">Gathering preferences from the squad.</p>
              </div>

              <div className={`relative pl-9 ${trip.all_ready ? "" : "opacity-40"}`}>
                <div className="absolute left-0 top-0.5 size-6 rounded-full bg-slate-100 flex items-center justify-center text-slate-400 shadow-sm">
                  <Shield size={12} />
                </div>
                <h4 className="font-extrabold text-slate-900 text-sm leading-none mb-1">Scouting destinations</h4>
                <p className="text-[13px] text-slate-500 font-medium">AI picks the best spots for your group.</p>
              </div>
            </div>
          </section> */}
        </div>
      </div>
    </main>
  )
}

export default TripLobby
