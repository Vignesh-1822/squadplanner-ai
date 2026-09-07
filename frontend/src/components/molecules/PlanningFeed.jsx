import { Check, Circle } from "lucide-react"
import { feedWindow } from "@/lib/planningSteps"

/**
 * The fixed-height status feed. Only FEED_WINDOW rows are ever on screen; as the run advances
 * the window slides and whatever leaves the top edge dissolves into the mask rather than the
 * list growing without bound.
 */
const PlanningFeed = ({ furthest, percent }) => {
  const rows = feedWindow(furthest)

  return (
    <div className="w-full space-y-6">
      <div className="w-full bg-slate-200/60 h-4 rounded-full overflow-hidden">
        <div
          className="bg-primary h-full rounded-full transition-all duration-700 ease-out"
          style={{ width: `${percent}%` }}
        />
      </div>

      <div
        className="flex flex-col gap-3 text-left h-[268px] overflow-hidden"
        style={{ maskImage: "linear-gradient(to bottom, transparent 0%, black 20%, black 100%)",
                 WebkitMaskImage: "linear-gradient(to bottom, transparent 0%, black 20%, black 100%)" }}
      >
        {rows.map(({ node, label, state }) => {
          if (state === "active") {
            return (
              <div
                key={node}
                className="flex items-center gap-4 p-4 rounded-2xl bg-primary/20 border border-primary/40 shrink-0 transition-all duration-500"
              >
                <div className="size-5 border-2 border-slate-900 border-t-transparent rounded-full animate-spin shrink-0" />
                <span className="text-slate-900 font-bold text-sm">{label}</span>
              </div>
            )
          }

          if (state === "done") {
            return (
              <div
                key={node}
                className="flex items-center gap-4 p-4 rounded-2xl bg-white/50 border border-white/70 shrink-0 transition-all duration-500"
              >
                <Check size={18} className="text-primary shrink-0" strokeWidth={3} />
                <span className="text-slate-700 font-medium text-sm">{label}</span>
              </div>
            )
          }

          return (
            <div key={node} className="flex items-center gap-4 p-4 rounded-2xl opacity-40 shrink-0">
              <Circle size={18} className="text-slate-400 shrink-0" />
              <span className="text-slate-600 font-medium text-sm">{label}</span>
            </div>
          )
        })}
      </div>

      <p className="text-sm font-medium uppercase tracking-widest text-slate-400 text-center">
        {percent}% Complete
      </p>
    </div>
  )
}

export default PlanningFeed
