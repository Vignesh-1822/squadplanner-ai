import { MapPin, Calendar } from "lucide-react"
import StatusBadge from "@/atoms/StatusBadge"
import AvatarStack from "@/atoms/AvatarStack"

const TripCard = ({ trip }) => {
  const { title, destination, date, image, members = [], status = "draft" } = trip

  return (
    <div className="group relative rounded-2xl overflow-hidden cursor-pointer">
      {/* Background image */}
      <div
        className="w-full h-40 bg-cover bg-center transition-transform duration-500 group-hover:scale-105"
        style={{ backgroundImage: image ? `url(${image})` : undefined, backgroundColor: image ? undefined : "var(--surface-container-high)" }}
      />

      {/* Gradient overlay */}
      <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/20 to-transparent" />

      {/* Status badge */}
      <div className="absolute top-3 left-3">
        <StatusBadge label={status} variant={status} />
      </div>

      {/* Bottom info */}
      <div className="absolute bottom-0 left-0 right-0 p-3">
        <p className="text-white font-bold text-sm leading-tight truncate">{title}</p>
        <div className="flex items-center gap-2 mt-1">
          <div className="flex items-center gap-1 text-white/70 text-[11px]">
            <MapPin size={10} />
            {destination}
          </div>
          {date && (
            <div className="flex items-center gap-1 text-white/70 text-[11px]">
              <Calendar size={10} />
              {date}
            </div>
          )}
        </div>
        {members.length > 0 && (
          <div className="mt-2">
            <AvatarStack names={members} max={3} />
          </div>
        )}
      </div>
    </div>
  )
}

export default TripCard
