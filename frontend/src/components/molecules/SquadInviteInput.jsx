import { useState } from "react"
import { X, UserPlus } from "lucide-react"

const COLORS = ["bg-violet-400", "bg-sky-400", "bg-emerald-400", "bg-rose-400", "bg-amber-400"]

const SquadInviteInput = ({ members, onAdd, onRemove }) => {
  const [value, setValue] = useState("")

  const handleKeyDown = (e) => {
    if ((e.key === "Enter" || e.key === ",") && value.trim()) {
      e.preventDefault()
      onAdd(value.trim())
      setValue("")
    }
  }

  return (
    <div>
      <label className="block text-[11px] font-bold uppercase tracking-widest text-gray-400 mb-2">
        Invite Your Squad
      </label>

      {/* Input */}
      <div className="flex items-center gap-2 border border-gray-200 rounded-xl px-3 py-2.5 bg-white/60 focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/20 transition-all">
        <UserPlus size={15} className="text-gray-400 flex-shrink-0" />
        <input
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Email or username"
          className="flex-1 bg-transparent text-sm text-gray-700 placeholder:text-gray-400 outline-none"
        />
      </div>

      {/* Chips */}
      {members.length > 0 && (
        <div className="flex flex-wrap gap-2 mt-2.5">
          {members.map((m, i) => (
            <div
              key={m}
              className="flex items-center gap-1.5 pl-1 pr-2 py-1 rounded-full bg-white border border-gray-200 shadow-sm"
            >
              <div className={`w-5 h-5 rounded-full ${COLORS[i % COLORS.length]} flex items-center justify-center text-white text-[9px] font-black`}>
                {m[0].toUpperCase()}
              </div>
              <span className="text-xs font-medium text-gray-700">{m}</span>
              <button
                onClick={() => onRemove(m)}
                className="text-gray-400 hover:text-gray-600 transition-colors ml-0.5"
              >
                <X size={11} />
              </button>
            </div>
          ))}
        </div>
      )}

      <p className="text-[11px] text-gray-400 mt-1.5">Press Enter or comma to add</p>
    </div>
  )
}

export default SquadInviteInput
