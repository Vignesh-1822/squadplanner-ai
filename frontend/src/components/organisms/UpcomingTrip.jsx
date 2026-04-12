import FeaturedTripCard from "@/molecules/FeaturedTripCard"
import EmptyTripsCard from "@/molecules/EmptyTripsCard"

const MOCK_UPCOMING = {
  id: "upcoming-1",
  title: "Nepal Adventure",
  destination: "Kathmandu, Nepal",
  date: "Jun 2026",
  description: "8 days trekking through Annapurna with the squad. Base camp, chai stops, and zero phone signal.",
  members: ["Vignesh", "Arjun", "Meera", "Kiran", "Priya"],
  image: "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=600&q=80",
}

const UpcomingTrip = ({ trip = MOCK_UPCOMING }) => (
  <section className="h-full">
    <div className="flex items-center justify-between mb-3">
      <h2 className="text-base font-black text-on-surface">Upcoming Trip</h2>
      <a href="/trips" className="text-xs font-bold text-primary hover:text-primary-dim transition-colors">
        View all
      </a>
    </div>
    <div className="h-[220px]">
      {trip ? <FeaturedTripCard trip={trip} /> : <EmptyTripsCard />}
    </div>
  </section>
)

export default UpcomingTrip
