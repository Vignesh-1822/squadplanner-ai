import { useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { Wallet, Luggage, Lock, Users, CalendarRange, PlusCircle, Trash2 } from "lucide-react"
import PreferenceSlider from "@/molecules/PreferenceSlider"
import AirportSelect from "@/atoms/AirportSelect"
import { DatePicker, ConfigProvider } from "antd"
import dayjs from "dayjs"
import { submitPreferences } from "@/services/ApiList"
import { buildPreferencesPayload, DIETARY_OPTIONS } from "@/lib/tripPayload"

// Keys must match backend/data/destinations.json -> vibe_tags. Labels are ours.
const DEFAULT_VIBES = [
  { key: "outdoor", label: "Nature & Outdoors", value: 50 },
  { key: "food", label: "Food & Dining", value: 100 },
  { key: "nightlife", label: "Nightlife", value: 50 },
  { key: "urban", label: "Urban Exploration", value: 50 },
  { key: "shopping", label: "Shopping", value: 25 },
]

const TripPreferences = () => {
  const navigate = useNavigate()
  const { tripId } = useParams()
  const queryClient = useQueryClient()
  const [vibes, setVibes] = useState(DEFAULT_VIBES)
  const [airport, setAirport] = useState("")
  const [budget, setBudget] = useState("")
  const [carryOn, setCarryOn] = useState(false)
  const [dietary, setDietary] = useState([])
  const [notes, setNotes] = useState("")

  // Date windows list state
  const [dateWindows, setDateWindows] = useState([
    { start_date: "2026-07-15", end_date: "2026-07-30" },
    { start_date: "2026-08-05", end_date: "2026-08-20" }
  ])

  const updateVibe = (key, value) =>
    setVibes((prev) => prev.map((v) => (v.key === key ? { ...v, value } : v)))

  const toggleDietary = (key) =>
    setDietary((prev) => (prev.includes(key) ? prev.filter((d) => d !== key) : [...prev, key]))

  const addDateWindow = () => {
    setDateWindows((prev) => [...prev, { start_date: "", end_date: "" }])
  }

  const removeDateWindow = (index) => {
    setDateWindows((prev) => prev.filter((_, i) => i !== index))
  }

  const updateDateWindowRange = (index, startDateStr, endDateStr) => {
    setDateWindows((prev) =>
      prev.map((d, i) =>
        i === index ? { ...d, start_date: startDateStr || "", end_date: endDateStr || "" } : d
      )
    )
  }

  const { mutate: savePreferences, isPending } = useMutation({
    mutationFn: (payload) => submitPreferences(tripId, payload),
    onSuccess: () => {
      toast.success("Preferences saved. You're ready to roll.")
      // Start the refetch before navigating, so the lobby doesn't paint a cached copy of
      // itself still asking for the preferences we just submitted.
      queryClient.invalidateQueries({ queryKey: ["trip", tripId] })
      navigate(`/trips/${tripId}/lobby`)
    },
    // The backend writes these messages for users — 409 once planning has started,
    // 422 for a bad payload — so show them as-is rather than inventing our own.
    onError: (error) => toast.error(error.message),
  })

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!tripId) {
      toast.error("No trip selected. Start by creating one.")
      navigate("/trips/new")
      return
    }
    savePreferences(
      buildPreferencesPayload({ vibes, airport, budget, carryOn, dietary, notes, dateWindows })
    )
  }

  // Validate form required fields (Personal Notes is optional)
  const isFormValid =
    airport &&
    budget &&
    dateWindows.length > 0 &&
    dateWindows.every((w) => w.start_date && w.end_date)

  return (
    <main className="flex-1 min-h-0 overflow-y-auto px-8 pb-8 pt-2">
      <div className="max-w-3xl mx-auto">

        {/* Title Header */}
        <div className="mb-6">
          <p className="text-[11px] font-bold uppercase tracking-widest text-gray-400 mb-1">
            Personalize your journey
          </p>
          <h1 className="text-4xl font-black text-gray-900 italic leading-tight">
            Trip Preferences
          </h1>
        </div>

        {/* Form Container */}
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">

          {/* Scrollable Options Container (Constrained to max height) */}
          <div className="max-h-[520px] overflow-y-auto pr-2 space-y-4 mb-2 border-b border-slate-100 pb-4 min-h-0">

            {/* Travel Vibes */}
            <section className="bg-white/40 backdrop-blur-md rounded-2xl border border-white/60 p-6 shadow-sm">
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

            {/* Date Windows */}
            <ConfigProvider
              theme={{
                token: {
                  colorPrimary: "#0f172a", // Slate for active selected cell background
                  borderRadius: 12,
                  fontFamily: "Geist Variable, Inter, sans-serif",
                  colorBgContainer: "rgba(255, 255, 255, 0.6)",
                  colorBorder: "rgba(226, 232, 240, 0.8)",
                  colorTextPlaceholder: "#94a3b8",
                  controlHeight: 44, // Match our custom input height
                },
                components: {
                  DatePicker: {
                    activeBorderColor: "#afd528",
                    hoverBorderColor: "#d1f94d",
                    cellActiveWithRangeBg: "rgba(209, 249, 77, 0.2)",
                    cellHoverWithRangeBg: "rgba(209, 249, 77, 0.1)",
                  }
                }
              }}
            >
              <section className="bg-white/40 backdrop-blur-md rounded-2xl border border-white/60 p-6 shadow-sm">
                <h2 className="text-lg font-black text-gray-800 italic flex items-center gap-2 mb-5">
                  <CalendarRange size={20} className="text-primary" />
                  Date Windows
                </h2>

                {/* Scrollable date window list */}
                <div className="space-y-3 mb-4 max-h-[220px] overflow-y-auto pr-1">
                  {dateWindows.map((window, idx) => (
                    <div key={idx} className="flex items-center gap-4 p-4 rounded-xl bg-white/40 border border-slate-200/50 shadow-sm">
                      <div className="flex-grow flex flex-col">
                        <label className="block text-[10px] font-bold uppercase tracking-widest text-gray-400 mb-1.5">
                          Date Range {idx + 1}
                        </label>
                        <DatePicker.RangePicker
                          value={[
                            window.start_date ? dayjs(window.start_date) : null,
                            window.end_date ? dayjs(window.end_date) : null
                          ]}
                          onChange={(dates, dateStrings) => {
                            updateDateWindowRange(idx, dateStrings[0], dateStrings[1])
                          }}
                          className="w-full h-11 rounded-xl border border-slate-200/50 bg-white/60 text-slate-700 hover:border-slate-300 focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/20 transition-all font-semibold"
                        />
                      </div>
                      <button
                        type="button"
                        onClick={() => removeDateWindow(idx)}
                        className="text-slate-400 hover:text-red-500 transition-colors self-end mb-1"
                      >
                        <Trash2 size={18} />
                      </button>
                    </div>
                  ))}
                </div>

                <button
                  type="button"
                  onClick={addDateWindow}
                  className="w-full py-4 border-2 border-dashed border-primary/45 hover:border-primary rounded-xl text-primary font-bold hover:bg-primary/5 transition-all flex items-center justify-center gap-2 text-sm"
                >
                  <PlusCircle size={16} />
                  Add Another Date Range
                </button>
              </section>
            </ConfigProvider>

            {/* Logistics + Personal Notes */}
            <div className="grid grid-cols-2 gap-4">
              <section className="bg-white/40 backdrop-blur-md rounded-2xl border border-white/60 p-6 flex flex-col gap-4 shadow-sm">
                <h2 className="text-lg font-black text-gray-800 italic">Logistics</h2>

                <div>
                  <label className="block text-[11px] font-bold uppercase tracking-widest text-gray-400 mb-2">
                    Starting Airport
                  </label>
                  <AirportSelect
                    value={airport}
                    onChange={setAirport}
                    placeholder="Select your departure airport"
                  />
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
                      className="flex-1 bg-transparent text-sm text-slate-700 placeholder:text-slate-400 outline-none"
                      required
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

              <section className="bg-white/40 backdrop-blur-md rounded-2xl border border-white/60 p-6 flex flex-col gap-4 shadow-sm">
                <h2 className="text-lg font-black text-gray-800 italic">Personal Notes</h2>

                <div>
                  <label className="block text-[11px] font-bold uppercase tracking-widest text-gray-400 mb-2">
                    Dietary Restrictions
                  </label>
                  <div className="flex flex-wrap gap-2">
                    {DIETARY_OPTIONS.map(({ key, label }) => {
                      const active = dietary.includes(key)
                      return (
                        <button
                          key={key}
                          type="button"
                          onClick={() => toggleDietary(key)}
                          aria-pressed={active}
                          className={`px-3 py-1.5 rounded-full text-[11px] font-bold uppercase tracking-wider border transition-all active:scale-95 ${
                            active
                              ? "bg-primary text-black border-primary shadow-sm"
                              : "bg-white/60 text-slate-500 border-gray-200 hover:border-primary/50"
                          }`}
                        >
                          {label}
                        </button>
                      )
                    })}
                  </div>
                </div>

                <div className="flex flex-col flex-1">
                  <label className="block text-[11px] font-bold uppercase tracking-widest text-gray-400 mb-2">
                    Special Requirements
                  </label>
                  <textarea
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    placeholder="Any allergies, mobility needs, or must-see spots?"
                    rows={4}
                    className="flex-1 w-full border border-gray-200 rounded-xl px-3 py-2.5 bg-white/60 focus:border-primary focus:ring-2 focus:ring-primary/20 text-sm text-gray-700 placeholder:text-gray-400 outline-none resize-none transition-all"
                  />
                </div>
              </section>
            </div>
          </div>

          {/* Action Footer button directly below the container */}
          <div className="flex justify-end mt-2 shrink-0">
            <button
              type="submit"
              disabled={!isFormValid || isPending}
              className="px-8 py-3 rounded-xl bg-primary text-black font-bold text-sm hover:bg-primary-dim transition-colors volt-glow disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-primary"
            >
              {isPending ? "Saving..." : "Save Preferences"}
            </button>
          </div>

        </form>

        <div className="flex items-center justify-center gap-6 mt-4 text-xs text-gray-400 shrink-0">
          <span className="flex items-center gap-1.5"><Lock size={11} /> End-to-end encrypted</span>
          <span className="flex items-center gap-1.5"><Users size={11} /> Shared with your squad</span>
        </div>

      </div>
    </main>
  )
}

export default TripPreferences
