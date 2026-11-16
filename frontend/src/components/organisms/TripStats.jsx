import { BarChart3, Plane, Hotel, Wallet, Users } from "lucide-react"
import { useAuth } from "@/store/authStore"
import {
  formatMoney,
  tripSpend,
  findMemberForUser,
  memberCostBreakdown,
  squadUtilisationRange,
} from "@/lib/itinerary"

/**
 * Quick Stats.
 *
 * Led by what the trip costs *you*, because that is the number a member acts on — everyone pays
 * a different share of a different budget, so a group average is a figure nobody actually pays.
 * Group totals stay, clearly scoped, underneath. Falls back to the group view for anyone not on
 * the trip.
 */
const TripStats = ({ itinerary }) => {
  const { user } = useAuth()
  const spend = tripSpend(itinerary)
  const me = findMemberForUser(itinerary?.members || [], user)
  const mine = memberCostBreakdown(itinerary, me)
  const range = squadUtilisationRange(itinerary)

  const percentOfMyBudget =
    mine?.utilisation != null ? Math.min(Math.round(mine.utilisation * 100), 100) : null
  const groupPercent =
    spend.budget > 0 ? Math.min(Math.round((spend.total / spend.budget) * 100), 100) : 0

  const headlineLabel = mine ? "Your share" : "Trip budget status"
  const headlineValue = mine ? mine.cost : spend.total
  const headlineBudget = mine ? mine.budget : spend.budget
  const headlinePercent = mine ? percentOfMyBudget ?? 0 : groupPercent
  const comfortable = headlinePercent <= 75

  return (
    <section className="bg-white/60 backdrop-blur-xl rounded-3xl border border-white/70 shadow-sm p-6 flex flex-col justify-between min-h-[380px]">
      <div>
        <header className="flex items-center justify-between gap-3 mb-6">
          <h2 className="flex items-center gap-2.5 text-xl font-black text-slate-900 tracking-tight">
            <BarChart3 size={22} className="text-primary fill-primary" />
            Quick Stats
          </h2>
        </header>

        <div className="space-y-6">
          <div>
            <div className="flex justify-between items-baseline mb-2">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
                {headlineLabel}
              </span>
              <span className="text-sm font-black text-slate-900">
                {formatMoney(headlineValue)}{" "}
                <span className="text-slate-400 font-normal">
                  / {headlineBudget > 0 ? formatMoney(headlineBudget) : "Flexible"}
                </span>
              </span>
            </div>

            <div className="h-3.5 w-full bg-slate-100 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ${
                  comfortable ? "bg-primary" : "bg-amber-400"
                }`}
                style={{ width: `${Math.max(headlinePercent, 8)}%` }}
              />
            </div>

            <p className="text-[11px] mt-2 text-[#ff71cf] font-bold italic underline decoration-wavy">
              {mine
                ? `You're using ${headlinePercent}% of the budget you set`
                : spend.budget > 0
                ? comfortable
                  ? "Pacing comfortably under our target budget! 🎉"
                  : "We are slightly over our target budget!"
                : "Itinerary curated to squad preferences ✨"}
            </p>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="bg-primary/25 p-4 rounded-2xl border border-primary/30">
              <p className="text-[10px] font-black uppercase tracking-widest text-slate-600">
                {mine ? "Your flight" : "Avg / Person"}
              </p>
              <p className="text-2xl font-black text-slate-900 mt-1">
                {formatMoney(mine ? mine.flight : spend.total / Math.max((itinerary?.members || []).length, 1))}
              </p>
              {mine && (
                <p className="text-[10px] font-bold text-slate-500 mt-0.5">
                  + {formatMoney(mine.lodgingShare)} lodging
                </p>
              )}
            </div>

            {/* The squad's *spread*, not an average: fairness is about the gap between members,
                and averaging is exactly what hides it. Lower is better. */}
            <div className="bg-[#ff71cf]/10 p-4 rounded-2xl border border-[#ff71cf]/20">
              <p className="text-[10px] font-black uppercase tracking-widest text-slate-600">
                {range ? "Squad range" : "Lodging"}
              </p>
              <p className="text-2xl font-black text-[#ff71cf] mt-1">
                {range ? `${range.min}–${range.max}%` : formatMoney(spend.hotel)}
              </p>
              {range && (
                <p className="text-[10px] font-bold text-slate-500 mt-0.5">
                  {range.passed ? "of budget · fair split" : "of budget · uneven"}
                </p>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="pt-4 border-t border-slate-100">
        <p className="flex items-center gap-1.5 text-[10px] font-black uppercase tracking-widest text-slate-400 mb-2">
          <Users size={11} className="text-primary" />
          Group totals
        </p>
        <div className="grid grid-cols-3 gap-2 text-center">
          <div>
            <p className="flex items-center justify-center gap-1 text-[10px] font-bold uppercase tracking-wider text-slate-400">
              <Plane size={10} /> Flights
            </p>
            <p className="text-xs font-black text-slate-800">{formatMoney(spend.flights)}</p>
          </div>
          <div>
            <p className="flex items-center justify-center gap-1 text-[10px] font-bold uppercase tracking-wider text-slate-400">
              <Hotel size={10} /> Lodging
            </p>
            <p className="text-xs font-black text-slate-800">{formatMoney(spend.hotel)}</p>
          </div>
          <div>
            <p className="flex items-center justify-center gap-1 text-[10px] font-bold uppercase tracking-wider text-slate-400">
              <Wallet size={10} /> Daily
            </p>
            <p className="text-xs font-black text-slate-800">{formatMoney(spend.daily)}</p>
          </div>
        </div>
      </div>
    </section>
  )
}

export default TripStats
