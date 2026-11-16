/** Day selector across the top of the itinerary. */
const DayPills = ({ days, activeDay, onSelect }) => (
  <div className="flex items-center gap-2 overflow-x-auto pb-1">
    {days.map((day) => {
      const isActive = day.day_number === activeDay
      return (
        <button
          key={day.day_number}
          type="button"
          onClick={() => onSelect(day.day_number)}
          className={`shrink-0 px-4 py-2 rounded-full text-xs font-black uppercase tracking-widest transition-all active:scale-95 cursor-pointer ${
            isActive
              ? "bg-primary text-slate-900 shadow-sm volt-glow"
              : "bg-white/60 text-slate-500 border border-slate-200/70 hover:text-slate-900"
          }`}
        >
          Day {day.day_number}
        </button>
      )
    })}
  </div>
)

export default DayPills
