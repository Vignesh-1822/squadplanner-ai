import { ChevronLeft, ChevronRight } from "lucide-react"

const MONTHS = ["May", "Jun", "Jul", "Aug", "Sep", "Oct"]

/* Mock trip markers: { month index 0-5, day } */
const TRIP_DOTS = [
  { month: 0, day: 3,  label: "Vienna",      sub: "01 - 03 May" },
  { month: 2, day: 26, label: "Paris, Fr.",   sub: "26 - 24 Jul", avatar: true },
  { month: 3, day: 25, label: "Bali Solo Trip", sub: "25 Sep - 31 Oct", avatar: true },
]

const CalendarWidget = ({ year = 2025 }) => (
  <div className="bg-white/40 backdrop-blur-md rounded-2xl p-4 h-full border border-white/50">
    {/* Header */}
    <div className="flex items-center justify-between mb-4">
      <div className="flex items-center gap-1.5 text-on-surface-variant text-xs">
        <span className="text-base">📅</span>
        <span className="font-semibold">Calendar</span>
      </div>
      <div className="flex items-center gap-2 text-sm font-bold text-on-surface">
        <button className="text-on-surface-variant hover:text-on-surface"><ChevronLeft size={14} /></button>
        May – Oct
        <button className="text-on-surface-variant hover:text-on-surface"><ChevronRight size={14} /></button>
        <span className="text-on-surface-variant font-normal">{year}</span>
      </div>
    </div>

    {/* Month strip */}
    <div className="grid grid-cols-6 gap-1 mb-3">
      {MONTHS.map((m) => (
        <div key={m} className="text-center text-[11px] font-bold text-on-surface-variant uppercase tracking-wide">
          {m}
        </div>
      ))}
    </div>

    {/* Trip entries */}
    <div className="space-y-2">
      {TRIP_DOTS.map((t, i) => (
        <div key={i} className="flex items-center gap-2 group">
          {/* Month column indicator */}
          <div className="grid grid-cols-6 gap-1 flex-1">
            {MONTHS.map((_, mi) => (
              <div key={mi} className="flex justify-center">
                {mi === t.month && (
                  <div className="w-6 h-6 rounded-full bg-surface-container-high border-2 border-surface-bright flex items-center justify-center text-[10px] font-bold text-on-surface">
                    {t.day}
                  </div>
                )}
              </div>
            ))}
          </div>
          {/* Label */}
          <div className="min-w-[100px]">
            <div className="flex items-center gap-1">
              {t.avatar && (
                <div className="w-4 h-4 rounded-full bg-primary text-black text-[8px] flex items-center justify-center font-bold">V</div>
              )}
              <span className="text-xs font-semibold text-on-surface truncate">{t.label}</span>
            </div>
            <span className="text-[10px] text-on-surface-variant">{t.sub}</span>
          </div>
        </div>
      ))}
    </div>
  </div>
)

export default CalendarWidget
