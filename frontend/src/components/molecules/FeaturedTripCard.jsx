import { MapPin, Users, ArrowRight } from "lucide-react"
import { Link } from "react-router-dom"
import AvatarStack from "@/atoms/AvatarStack"

const FeaturedTripCard = ({ trip }) => {
  const { id, title, destination, date, image, members = [], description } = trip

  return (
    <div className="relative rounded-3xl overflow-hidden h-full min-h-[220px] cursor-pointer group volt-glow">
      {/* Background */}
      <div
        className="absolute inset-0 bg-cover bg-center transition-transform duration-700 group-hover:scale-105"
        style={{
          backgroundImage: image ? `url(${image})` : undefined,
          background: image
            ? undefined
            : "linear-gradient(135deg, var(--secondary) 0%, #2d3c12 100%)",
        }}
      />
      <div className="absolute inset-0 bg-gradient-to-br from-black/30 via-transparent to-black/60" />

      {/* Volt green accent strip */}
      <div className="absolute top-0 left-0 right-0 h-1 bg-primary" />

      <div className="relative h-full p-5 flex flex-col justify-between">
        {/* Top row */}
        <div className="flex items-start justify-between">
          <div>
            <span className="text-[11px] font-bold uppercase tracking-widest bg-primary text-black px-2 py-0.5 rounded-full">
              Active Trip
            </span>
          </div>
          {members.length > 0 && (
            <div className="flex items-center gap-2">
              <AvatarStack names={members} max={4} />
              <span className="text-white/70 text-[11px]">
                <Users size={10} className="inline mr-0.5" />
                {members.length}
              </span>
            </div>
          )}
        </div>

        {/* Bottom content */}
        <div>
          <h2 className="text-white font-black text-2xl leading-tight">{title}</h2>
          <div className="flex items-center gap-1.5 mt-1 text-white/80 text-xs">
            <MapPin size={12} />
            <span>{destination}</span>
            {date && <span className="text-white/50">· {date}</span>}
          </div>
          {description && (
            <p className="text-white/60 text-xs mt-2 line-clamp-2">{description}</p>
          )}
          <Link
            to={`/trips/${id}`}
            className="inline-flex items-center gap-1.5 mt-3 text-primary text-xs font-bold hover:gap-2.5 transition-all"
          >
            View trip <ArrowRight size={12} />
          </Link>
        </div>
      </div>
    </div>
  )
}

export default FeaturedTripCard
