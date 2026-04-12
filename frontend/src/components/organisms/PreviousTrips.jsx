import { Link } from "react-router-dom"
import TripStatsBar from "@/molecules/TripStatsBar"

const MOCK_TRIPS = [
  {
    id: "1",
    title: "Japan",
    dates: "12 – 19 Oct",
    tags: ["Cultural", "Solo", "Roadtrip"],
    image: "https://images.unsplash.com/photo-1540959733332-eab4deabeeaf?w=400&q=80",
  },
  {
    id: "2",
    title: "Bali",
    dates: "Dec 2024",
    image: "https://images.unsplash.com/photo-1537996194471-e657df975ab4?w=400&q=80",
  },
  {
    id: "3",
    title: "Nepal",
    dates: "Jun 2026",
    image: "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=400&q=80",
  },
]

const TripThumb = ({ trip }) => (
  <div
    className="relative rounded-xl overflow-hidden flex-shrink-0 w-24 h-full bg-cover bg-center"
    style={{ backgroundImage: `url(${trip.image})` }}
  >
    <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent" />
    <div className="absolute bottom-2 left-2 right-2">
      <p className="text-white font-black text-xs leading-none">{trip.title}</p>
      <p className="text-white/60 text-[10px] mt-0.5">{trip.dates}</p>
    </div>
    {trip.tags && (
      <div className="absolute top-2 left-2 flex flex-col gap-1">
        {trip.tags.slice(0, 2).map((tag) => (
          <span key={tag} className="bg-primary/90 text-black text-[9px] font-bold px-1.5 py-0.5 rounded-full">
            {tag}
          </span>
        ))}
      </div>
    )}
  </div>
)

const PreviousTrips = ({ trips = MOCK_TRIPS }) => (
  <div className="bg-white/40 backdrop-blur-md rounded-2xl p-4 border border-white/50 h-full">
    {/* Header */}
    <div className="flex items-center justify-between mb-3">
      <div className="flex items-center gap-1.5 text-xs text-on-surface-variant font-semibold">
        <span>🕐</span> Previous trips
      </div>
      <Link to="/trips" className="text-xs font-bold text-on-surface-variant hover:text-primary transition-colors">
        See all
      </Link>
    </div>

    {/* Trip thumbnails */}
    <div className="flex gap-2 h-[130px] mb-4">
      {trips.map((trip) => (
        <TripThumb key={trip.id} trip={trip} />
      ))}
    </div>

    {/* Stats */}
    <TripStatsBar />
  </div>
)

export default PreviousTrips
