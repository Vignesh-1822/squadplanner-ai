import { useEffect } from "react"
import { useParams, useNavigate } from "react-router-dom"
import { useQuery, useMutation } from "@tanstack/react-query"
import { Users, ArrowRight, LogIn, AlertTriangle, CheckCircle2 } from "lucide-react"
import { toast } from "sonner"
import { getTripByInvite, joinTrip } from "@/services/ApiList"
import { useAuth } from "@/store/authStore"
import { MEMBER_PENDING } from "@/lib/tripStatus"

/** Where the emailed invite link lands. Public — guests arrive here signed out. */
export const PENDING_INVITE_KEY = "pendingInvite"

const AVATAR_COLORS = ["bg-orange-500", "bg-pink-500", "bg-purple-600", "bg-teal-500", "bg-blue-600"]

const Shell = ({ children }) => (
  <main className="flex-1 flex items-center justify-center px-4 py-10">
    <div className="bg-white/70 backdrop-blur-xl w-full max-w-lg rounded-[2rem] border border-white/85 shadow-xl shadow-primary/10 p-8 md:p-10 text-center">
      {children}
    </div>
  </main>
)

const JoinTrip = () => {
  const { inviteCode } = useParams()
  const navigate = useNavigate()
  const { user, loading: authLoading } = useAuth()

  const { data: trip, isLoading, error } = useQuery({
    queryKey: ["invite", inviteCode],
    queryFn: () => getTripByInvite(inviteCode),
    enabled: !!inviteCode,
    retry: false,
  })

  // Signed-out guests are sent to /auth and returned here afterwards, so the invite survives
  // the round trip through login.
  useEffect(() => {
    if (inviteCode) sessionStorage.setItem(PENDING_INVITE_KEY, inviteCode)
  }, [inviteCode])

  const { mutate: join, isPending: isJoining } = useMutation({
    mutationFn: () => joinTrip(trip.trip_id),
    onSuccess: () => {
      sessionStorage.removeItem(PENDING_INVITE_KEY)
      toast.success("You're in! Add your preferences next.")
      navigate(`/trips/${trip.trip_id}/preferences`)
    },
    onError: (err) => toast.error(err.message),
  })

  if (isLoading || authLoading) {
    return (
      <Shell>
        <p className="animate-pulse text-slate-500 font-medium">Looking up your invite...</p>
      </Shell>
    )
  }

  if (error || !trip) {
    return (
      <Shell>
        <div className="size-14 rounded-full bg-amber-100 flex items-center justify-center mx-auto mb-5">
          <AlertTriangle size={26} className="text-amber-500" />
        </div>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight mb-3">
          This invite doesn&apos;t work
        </h1>
        <p className="text-slate-500 text-sm font-medium">
          {error?.message || "The link may be mistyped, or the trip may no longer exist."}
        </p>
      </Shell>
    )
  }

  const members = trip.invited_members || []
  const me = user ? members.find((member) => member.email === user.email) : null
  const alreadyIn = !!me && me.status !== MEMBER_PENDING

  return (
    <Shell>
      <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-primary/20 text-slate-800 text-[10px] font-black uppercase tracking-widest mb-5">
        <Users size={12} />
        Squad invite
      </span>

      <h1 className="text-3xl md:text-4xl font-black tracking-tight text-slate-900 leading-none mb-3">
        You&apos;re invited to{" "}
        <span className="bg-primary px-2 inline-block -rotate-1">{trip.trip_name}</span>
      </h1>

      <p className="text-slate-500 text-sm font-medium mb-8">
        {trip.created_by ? `${trip.created_by} wants you on this trip.` : "Join the squad and add your preferences."}
      </p>

      {members.length > 0 && (
        <div className="flex items-center justify-center -space-x-3 mb-8">
          {members.slice(0, 5).map((member, index) => (
            <span
              key={member.email || index}
              title={member.email}
              className={`size-11 rounded-full ring-4 ring-white flex items-center justify-center text-white font-black shadow-sm ${
                AVATAR_COLORS[index % AVATAR_COLORS.length]
              }`}
            >
              {(member.email || "?")[0].toUpperCase()}
            </span>
          ))}
          {members.length > 5 && (
            <span className="size-11 rounded-full ring-4 ring-white bg-slate-100 text-slate-600 text-xs font-bold flex items-center justify-center">
              +{members.length - 5}
            </span>
          )}
        </div>
      )}

      {!user ? (
        <>
          <button
            type="button"
            onClick={() => navigate("/auth")}
            className="group inline-flex items-center gap-2 bg-slate-950 text-primary px-8 py-3.5 rounded-xl text-sm font-black uppercase tracking-widest transition-all hover:-translate-y-0.5 active:scale-95 cursor-pointer volt-glow"
          >
            <LogIn size={16} />
            Sign in to join
          </button>
          <p className="text-[11px] text-slate-400 font-medium mt-4">
            We&apos;ll bring you straight back here.
          </p>
        </>
      ) : alreadyIn ? (
        <>
          <p className="flex items-center justify-center gap-2 text-sm font-bold text-slate-700 mb-5">
            <CheckCircle2 size={16} className="text-green-600" />
            You&apos;re already part of this squad.
          </p>
          <button
            type="button"
            onClick={() => navigate(`/trips/${trip.trip_id}/lobby`)}
            className="group inline-flex items-center gap-2 bg-primary text-slate-900 px-8 py-3.5 rounded-xl text-sm font-black uppercase tracking-widest transition-all hover:-translate-y-0.5 active:scale-95 cursor-pointer"
          >
            Go to the lobby
            <ArrowRight size={16} className="transition-transform group-hover:translate-x-1" />
          </button>
        </>
      ) : (
        <button
          type="button"
          onClick={() => join()}
          disabled={isJoining}
          className="group inline-flex items-center gap-2 bg-primary text-slate-900 px-8 py-3.5 rounded-xl text-sm font-black uppercase tracking-widest transition-all hover:-translate-y-0.5 active:scale-95 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isJoining ? "Joining..." : "Join this squad"}
          <ArrowRight size={16} className="transition-transform group-hover:translate-x-1" />
        </button>
      )}
    </Shell>
  )
}

export default JoinTrip
