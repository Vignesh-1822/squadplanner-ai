import { User, MapPin } from "lucide-react"

const UserProfileCard = ({ name = "Vignesh", milesLabel = "140 Miles Traveled" }) => (
  <div className="relative rounded-2xl overflow-hidden h-full bg-gradient-to-br from-slate-600 via-slate-700 to-slate-900">
    {/* Subtle volt halo */}
    <div className="absolute top-0 right-0 w-32 h-32 rounded-full bg-primary/20 blur-2xl -translate-y-8 translate-x-8" />

    <div className="relative h-full flex flex-col justify-between p-4">
      {/* Top: account label */}
      <div className="flex items-center gap-1.5 text-white/60 text-xs font-medium">
        <span className="w-1.5 h-1.5 rounded-full bg-primary" />
        Account
      </div>

      {/* Center: avatar icon */}
      <div className="flex justify-center">
        <div className="w-16 h-16 rounded-full bg-white/10 border-2 border-white/20 flex items-center justify-center">
          <User size={28} className="text-white/80" />
        </div>
      </div>

      {/* Bottom: name + stat */}
      <div>
        <h2 className="text-white font-black text-lg leading-tight uppercase tracking-wide">
          {name}
        </h2>
        <p className="flex items-center gap-1 text-white/50 text-xs mt-0.5">
          <MapPin size={10} />
          {milesLabel}
        </p>
      </div>
    </div>
  </div>
)

export default UserProfileCard
