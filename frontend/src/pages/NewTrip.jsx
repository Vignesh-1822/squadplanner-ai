import { useState } from "react"
import { useNavigate, Link } from "react-router-dom"
import { Flag } from "lucide-react"
import SquadInviteInput from "@/molecules/SquadInviteInput"

const NewTrip = () => {
  const navigate = useNavigate()
  const [tripName, setTripName] = useState("")
  const [members, setMembers] = useState([])

  const handleAddMember = (name) => {
    if (!members.includes(name)) setMembers((prev) => [...prev, name])
  }

  const handleRemoveMember = (name) => {
    setMembers((prev) => prev.filter((m) => m !== name))
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    navigate("/trips/preferences")
  }

  return (
    <main className="flex-1 flex items-center justify-center px-6 pb-8">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-4xl font-black text-gray-900 leading-tight">Plan a New Trip</h1>
          <p className="text-gray-500 text-sm mt-2">Set the stage for your next group adventure.</p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="bg-white/60 backdrop-blur-md rounded-2xl border border-white/80 shadow-sm p-6 flex flex-col gap-5"
        >
          <div>
            <label className="block text-[11px] font-bold uppercase tracking-widest text-gray-400 mb-2">
              Trip Name
            </label>
            <div className="flex items-center gap-2 border border-gray-200 rounded-xl px-3 py-2.5 bg-white/60 focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/20 transition-all">
              <Flag size={15} className="text-gray-400 flex-shrink-0" />
              <input
                type="text"
                value={tripName}
                onChange={(e) => setTripName(e.target.value)}
                placeholder="Tokyo Drift 2025"
                className="flex-1 bg-transparent text-sm text-gray-700 placeholder:text-gray-400 outline-none"
                required
              />
            </div>
          </div>

          <SquadInviteInput
            members={members}
            onAdd={handleAddMember}
            onRemove={handleRemoveMember}
          />

          <button
            type="submit"
            className="w-full py-3 rounded-xl bg-primary text-black font-bold text-sm flex items-center justify-center gap-2 hover:bg-primary-dim transition-colors volt-glow mt-1"
          >
            Create Trip 🚀
          </button>
        </form>
      </div>
    </main>
  )
}

export default NewTrip
