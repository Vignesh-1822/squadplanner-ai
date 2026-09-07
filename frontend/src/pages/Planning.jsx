import { useMemo, useState } from "react"
import { useParams, useNavigate } from "react-router-dom"
import { useMutation } from "@tanstack/react-query"
import { Sparkles, AlertTriangle } from "lucide-react"
import { toast } from "sonner"
import { streamUrl, confirmCity } from "@/services/ApiList"
import { useEventStream } from "@/hooks"
import { planningProgress } from "@/lib/planningSteps"
import PlanningFeed from "@/molecules/PlanningFeed"
import DestinationCard from "@/molecules/DestinationCard"
import DestinationDetail from "@/molecules/DestinationDetail"

/** Scores are raw similarity values, so they only mean anything relative to the best candidate. */
function matchPercents(candidates) {
  const top = Math.max(...candidates.map((c) => c.score || 0), 0)
  return candidates.map((c) => (top > 0 ? Math.round((c.score / top) * 100) : 100))
}

const Planning = () => {
  const { tripId } = useParams()
  const navigate = useNavigate()

  const [candidates, setCandidates] = useState(null)
  const [detail, setDetail] = useState(null)
  const [completed, setCompleted] = useState(null)
  const [failure, setFailure] = useState(null)

  const url = useMemo(() => (tripId ? streamUrl(tripId) : null), [tripId])

  const { events } = useEventStream(url, {
    enabled: !!tripId,
    closeOn: ["TRIP_COMPLETE", "ERROR"],
    onEvent: (frame) => {
      if (frame.event_type === "HITL_REQUIRED") setCandidates(frame.data?.candidate_destinations || [])
      if (frame.event_type === "TRIP_COMPLETE") setCompleted(frame.data)
      if (frame.event_type === "ERROR") setFailure(frame.data?.message || "Planning failed.")
    },
  })

  const { mutate: pickCity, isPending: isConfirming } = useMutation({
    mutationFn: (destination) =>
      confirmCity(tripId, {
        selected_destination: destination.name,
        selected_destination_coords: destination.coords,
      }),
    // The same stream is still open; the backend picks the choice up and carries on.
    onSuccess: (_data, destination) => {
      setCandidates(null)
      setDetail(null)
      toast.success(`${destination.name} it is. Building your itinerary...`)
    },
    onError: (error) => toast.error(error.message),
  })

  const nodeEvents = events.filter((event) => event.event_type === "NODE_PROGRESS")
  const { furthest, percent } = planningProgress(nodeEvents)

  if (failure) {
    return (
      <main className="flex-1 flex items-center justify-center px-6 py-12">
        <div className="bg-white/60 backdrop-blur-xl rounded-[2rem] border border-white/70 shadow-sm p-12 text-center max-w-lg">
          <div className="size-16 rounded-full bg-red-100 flex items-center justify-center mx-auto mb-5">
            <AlertTriangle size={28} className="text-red-500" />
          </div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight mb-3">Planning hit a snag</h1>
          <p className="text-slate-500 text-sm font-medium mb-6">{failure}</p>
          <button
            type="button"
            onClick={() => navigate(`/trips/${tripId}/lobby`)}
            className="bg-slate-900 text-primary font-black text-xs uppercase tracking-widest px-6 py-3 rounded-xl hover:scale-[1.02] active:scale-95 transition-all cursor-pointer"
          >
            Back to the lobby
          </button>
        </div>
      </main>
    )
  }

  if (completed) {
    const destination = completed.itinerary?.selected_destination
    return (
      <main className="flex-1 flex items-center justify-center px-6 py-12">
        <div className="bg-white/60 backdrop-blur-xl rounded-[2rem] border border-white/70 shadow-sm p-12 text-center max-w-2xl">
          <div className="size-16 rounded-full bg-primary flex items-center justify-center mx-auto mb-5 volt-glow">
            <Sparkles size={28} className="text-slate-900" />
          </div>
          <p className="text-[11px] font-black uppercase tracking-[0.3em] text-slate-400 mb-3">Your trip is ready</p>
          <h1 className="text-4xl font-black text-slate-900 tracking-tight mb-5">{destination}</h1>
          <p className="text-slate-600 font-medium leading-relaxed">{completed.trip_pitch}</p>
          {/* TODO(F3b): route to /trips/:tripId/itinerary for days, hotel, flights and refinements. */}
        </div>
      </main>
    )
  }

  if (candidates) {
    const percents = matchPercents(candidates)
    return (
      <main className="flex-1 max-w-6xl mx-auto w-full px-6 py-10 lg:px-12">
        <div className="mb-8">
          <p className="text-[11px] font-black uppercase tracking-[0.3em] text-slate-400 mb-2">Your turn, Vibe Master</p>
          <h1 className="text-3xl md:text-4xl font-black text-slate-900 tracking-tight mb-2">Curated Destinations</h1>
          <p className="text-slate-500 font-medium">
            We analysed your squad&apos;s preferences and found these matches. Pick one to keep planning.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {candidates.map((destination, index) => (
            <DestinationCard
              key={destination.id || index}
              destination={destination}
              matchPercent={percents[index]}
              onSelect={pickCity}
              onViewDetails={setDetail}
              disabled={isConfirming}
            />
          ))}
        </div>

        {detail && (
          <DestinationDetail
            destination={detail}
            matchPercent={percents[candidates.indexOf(detail)]}
            onSelect={pickCity}
            onClose={() => setDetail(null)}
            disabled={isConfirming}
          />
        )}
      </main>
    )
  }

  return (
    <main className="flex-1 flex items-center justify-center px-6 py-12">
      <div className="bg-white/60 backdrop-blur-xl rounded-[2rem] border border-white/70 shadow-sm p-10 md:p-12 w-full max-w-xl flex flex-col items-center gap-8">
        <div className="flex flex-col items-center gap-4 text-center">
          <div className="size-16 rounded-full bg-primary flex items-center justify-center volt-glow">
            <Sparkles size={28} className="text-slate-900" />
          </div>
          <div className="space-y-2">
            <h1 className="text-3xl md:text-4xl font-black text-slate-900 tracking-tight">
              Generating Your Trip Pitch
            </h1>
            <p className="text-slate-500 text-lg font-medium">Our AI agent is crafting the perfect getaway...</p>
          </div>
        </div>

        <PlanningFeed furthest={furthest} percent={percent} />
      </div>
    </main>
  )
}

export default Planning
