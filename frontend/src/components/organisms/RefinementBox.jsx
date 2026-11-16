import { useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Sparkles, RefreshCw } from "lucide-react"
import { toast } from "sonner"
import { refineTrip, refinementStreamUrl } from "@/services/ApiList"
import { useEventStream } from "@/hooks"

const EXAMPLES = ["Make Day 2 cheaper", "Swap the museum for something outdoors", "Add more food stops"]

/**
 * Natural-language edits to a finished itinerary.
 *
 * Two steps by design: the POST queues the edit and returns an id, then the stream runs the
 * graph again from the affected node. The updated itinerary arrives on REFINEMENT_COMPLETE and
 * is written straight into the cached trip result, so the page updates in place.
 */
const RefinementBox = ({ tripId }) => {
  const [message, setMessage] = useState("")
  const [refinementId, setRefinementId] = useState(null)
  const queryClient = useQueryClient()

  const { status } = useEventStream(refinementId ? refinementStreamUrl(tripId, refinementId) : null, {
    enabled: !!refinementId,
    closeOn: ["REFINEMENT_COMPLETE", "ERROR"],
    onEvent: (frame) => {
      if (frame.event_type === "REFINEMENT_COMPLETE") {
        queryClient.setQueryData(["trip-result", tripId], (previous) => ({
          ...(previous || {}),
          ...frame.data,
        }))
        setRefinementId(null)
        setMessage("")
        toast.success("Itinerary updated.")
      }
      if (frame.event_type === "ERROR") {
        setRefinementId(null)
        toast.error(frame.data?.message || "That refinement could not be applied.")
      }
    },
  })

  const { mutate: submit, isPending } = useMutation({
    mutationFn: () => refineTrip(tripId, message.trim()),
    onSuccess: (data) => {
      setRefinementId(data.refinement_id)
      toast.success("Reworking your itinerary...")
    },
    // 409 before completion, 422 for edits that would need a whole new trip — both written
    // for users, so they are surfaced unchanged.
    onError: (error) => toast.error(error.message),
  })

  const running = isPending || (!!refinementId && status !== "closed")

  return (
    <section className="bg-white/60 backdrop-blur-md rounded-2xl border border-white/70 shadow-sm p-5">
      <h2 className="flex items-center gap-2 text-sm font-black text-slate-900 uppercase tracking-wider mb-1">
        <Sparkles size={16} className="text-primary" />
        Tweak this trip
      </h2>
      <p className="text-slate-500 text-xs font-medium mb-4">
        Ask in plain English. The agent reruns only the part that changes.
      </p>

      <form
        onSubmit={(event) => {
          event.preventDefault()
          if (message.trim()) submit()
        }}
        className="flex flex-col gap-3"
      >
        <input
          type="text"
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          disabled={running}
          placeholder="Make Day 2 cheaper..."
          className="w-full border border-gray-200 rounded-xl px-3.5 py-2.5 bg-white/70 focus:border-primary focus:ring-2 focus:ring-primary/20 text-sm text-slate-700 placeholder:text-slate-400 outline-none transition-all disabled:opacity-50"
        />

        <div className="flex flex-wrap gap-1.5">
          {EXAMPLES.map((example) => (
            <button
              key={example}
              type="button"
              disabled={running}
              onClick={() => setMessage(example)}
              className="px-2.5 py-1 rounded-full bg-slate-100 text-slate-500 text-[10px] font-bold hover:bg-primary/20 hover:text-slate-800 transition-colors cursor-pointer disabled:opacity-50"
            >
              {example}
            </button>
          ))}
        </div>

        <button
          type="submit"
          disabled={running || !message.trim()}
          className="flex items-center justify-center gap-2 bg-slate-900 text-primary font-black text-xs uppercase tracking-widest px-6 py-3 rounded-xl transition-all hover:scale-[1.02] active:scale-95 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:scale-100"
        >
          {running && <RefreshCw size={14} className="animate-spin" />}
          {running ? "Reworking..." : "Apply change"}
        </button>
      </form>
    </section>
  )
}

export default RefinementBox
