import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { PlaneTakeoff, Wallet, Luggage, Lock, Users } from "lucide-react"
import PreferenceSlider from "@/molecules/PreferenceSlider"

const DEFAULT_VIBES = [
  { key: "nightlife", label: "Nightlife",         value: 50 },
  { key: "adventure", label: "Adventure",         value: 75 },
  { key: "shopping",  label: "Shopping",          value: 25 },
  { key: "food",      label: "Food & Dining",     value: 100 },
  { key: "urban",     label: "Urban Exploration", value: 50 },
  { key: "nature",    label: "Nature & Outdoors", value: 50 },
]

const TripPreferences = () => {
  const navigate = useNavigate()
  const [vibes, setVibes]     = useState(DEFAULT_VIBES)
  const [airport, setAirport] = useState("")
  const [budget, setBudget]   = useState("")
  const [carryOn, setCarryOn] = useState(false)
  const [notes, setNotes]     = useState("")

  const updateVibe = (key, value) =>
    setVibes((prev) => prev.map((v) => (v.key === key ? { ...v, value } : v)))

  const handleSubmit = (e) => {
    e.preventDefault()
    navigate("/dashboard")
  }

  return (
    <main className="flex-1 min-h-0 overflow-y-auto px-8 pb-8 pt-2">
      <div className="max-w-3xl mx-auto">

        <div className="mb-6">
          <p className="text-[11px] font-bold uppercase tracking-widest text-gray-400 mb-1">
            Personalize your journey
          </p>
          <h1 className="text-4xl font-black text-gray-900 italic leading-tight">
            Trip Preferences
          </h1>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">

          {/* Travel Vibes */}
          <section className="bg-white/40 backdrop-blur-md rounded-2xl border border-white/60 p-6">
            <h2 className="text-lg font-black text-gray-800 italic mb-5">Travel Vibes</h2>
            <div className="grid grid-cols-2 gap-x-10 gap-y-6">
              {vibes.map(({ key, label, value }) => (
                <PreferenceSlider
                  key={key}
                  label={label}
                  value={value}
                  onChange={(v) => updateVibe(key, v)}
                />
              ))}
            </div>
          </section>

          {/* Logistics + Personal Notes */}
          <div className="grid grid-cols-2 gap-4">
            <section className="bg-white/40 backdrop-blur-md rounded-2xl border border-white/60 p-6 flex flex-col gap-4">
              <h2 className="text-lg font-black text-gray-800 italic">Logistics</h2>

              <div>
                <label className="block text-[11px] font-bold uppercase tracking-widest text-gray-400 mb-2">
                  Starting Airport
                </label>
                <div className="flex items-center gap-2 border border-gray-200 rounded-xl px-3 py-2.5 bg-white/60 focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/20 transition-all">
                  <PlaneTakeoff size={14} className="text-gray-400 flex-shrink-0" />
                  <input
                    type="text"
                    value={airport}
                    onChange={(e) => setAirport(e.target.value)}
                    placeholder="e.g., JFK, London Heathrow"
                    className="flex-1 bg-transparent text-sm text-gray-700 placeholder:text-gray-400 outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-bold uppercase tracking-widest text-gray-400 mb-2">
                  Total Budget (USD)
                </label>
                <div className="flex items-center gap-2 border border-gray-200 rounded-xl px-3 py-2.5 bg-white/60 focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/20 transition-all">
                  <Wallet size={14} className="text-gray-400 flex-shrink-0" />
                  <input
                    type="number"
                    value={budget}
                    onChange={(e) => setBudget(e.target.value)}
                    placeholder="$500"
                    className="flex-1 bg-transparent text-sm text-gray-700 placeholder:text-gray-400 outline-none"
                  />
                </div>
              </div>

              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-sm font-semibold text-gray-700">
                  <Luggage size={15} className="text-gray-400" />
                  Carry-on Only
                </div>
                <button
                  type="button"
                  onClick={() => setCarryOn((v) => !v)}
                  className={`relative w-10 h-5 rounded-full transition-colors ${carryOn ? "bg-primary" : "bg-gray-200"}`}
                >
                  <span
                    className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${carryOn ? "translate-x-5" : "translate-x-0"}`}
                  />
                </button>
              </div>
            </section>

            <section className="bg-white/40 backdrop-blur-md rounded-2xl border border-white/60 p-6 flex flex-col gap-4">
              <h2 className="text-lg font-black text-gray-800 italic">Personal Notes</h2>
              <div className="flex flex-col flex-1">
                <label className="block text-[11px] font-bold uppercase tracking-widest text-gray-400 mb-2">
                  Special Requirements
                </label>
                <textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Any allergies, mobility needs, or must-see spots?"
                  rows={6}
                  className="flex-1 w-full border border-gray-200 rounded-xl px-3 py-2.5 bg-white/60 focus:border-primary focus:ring-2 focus:ring-primary/20 text-sm text-gray-700 placeholder:text-gray-400 outline-none resize-none transition-all"
                />
              </div>
            </section>
          </div>

          <div className="flex justify-end">
            <button
              type="submit"
              className="px-8 py-3 rounded-xl bg-primary text-black font-bold text-sm hover:bg-primary-dim transition-colors volt-glow"
            >
              Save Preferences
            </button>
          </div>
        </form>

        <div className="flex items-center justify-center gap-6 mt-4 text-xs text-gray-400">
          <span className="flex items-center gap-1.5"><Lock size={11} /> End-to-end encrypted</span>
          <span className="flex items-center gap-1.5"><Users size={11} /> Shared with your squad</span>
        </div>

      </div>
    </main>
  )
}

export default TripPreferences
