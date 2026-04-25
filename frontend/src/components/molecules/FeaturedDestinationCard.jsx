import { Settings2, MapPin, Users, Star } from "lucide-react"
import AvatarStack from "@/atoms/AvatarStack"

const TAGS = ["Montmartre", "Louvre", "Shopping"]

const FeaturedDestinationCard = ({
  city = "PARIS, FRANCE",
  dates = "28 Jul – 26 Jul",
  price = "$864",
  tags = TAGS,
  nights = "2 nights",
  destinations = "1 destination",
  members = ["V", "A"],
  image = "https://images.unsplash.com/photo-1502602898657-3e91760cbb34?w=600&q=80",
}) => (
  <div className="bg-white/40 backdrop-blur-md rounded-2xl p-4 h-full border border-white/50">
    {/* Header row */}
    <div className="flex items-start justify-between mb-3">
      <div>
        <h2 className="text-2xl font-black text-on-surface leading-tight italic">{city}</h2>
        <p className="text-xs text-on-surface-variant mt-0.5">{dates} · {price}</p>
      </div>
      <button className="w-7 h-7 flex items-center justify-center rounded-lg text-on-surface-variant hover:bg-surface-container transition-colors">
        <Settings2 size={14} />
      </button>
    </div>

    {/* Members + tags */}
    <div className="flex items-center gap-2 mb-3 flex-wrap">
      <AvatarStack names={members} max={3} />
      {tags.map((tag) => (
        <span key={tag} className="text-[11px] font-medium text-on-surface-variant bg-surface-container px-2 py-0.5 rounded-full">
          {tag}
        </span>
      ))}
    </div>

    {/* Photo strip */}
    <div className="grid grid-cols-3 gap-2 mb-3 h-[100px]">
      <div
        className="col-span-2 rounded-xl bg-cover bg-center"
        style={{ backgroundImage: `url(${image})` }}
      />
      <div className="flex flex-col gap-2">
        <div className="flex-1 rounded-xl bg-cover bg-center" style={{ backgroundImage: `url(https://images.unsplash.com/photo-1522093007474-d86e9bf7ba6f?w=200&q=80)` }} />
        <div className="flex-1 rounded-xl bg-cover bg-center" style={{ backgroundImage: `url(https://images.unsplash.com/photo-1499856871958-5b9627545d1a?w=200&q=80)` }} />
      </div>
    </div>

    {/* Footer */}
    <div className="flex items-center gap-3 text-xs text-on-surface-variant">
      <span className="flex items-center gap-1"><MapPin size={11} />{destinations}</span>
      <span>·</span>
      <span>{nights}</span>
      <span className="ml-auto flex items-center gap-1 text-primary font-bold">
        <Star size={11} fill="currentColor" /> Active
      </span>
    </div>
  </div>
)

export default FeaturedDestinationCard
