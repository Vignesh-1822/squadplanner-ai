import HomeHeader from "@/organisms/HomeHeader"
import UserProfileCard from "@/molecules/UserProfileCard"
import CalendarWidget from "@/molecules/CalendarWidget"
import FeaturedDestinationCard from "@/molecules/FeaturedDestinationCard"
import PreviousTrips from "@/organisms/PreviousTrips"
import EuropeMap from "@/organisms/EuropeMap"

const Home = () => (
  <div className="h-screen overflow-hidden flex flex-col">
    <HomeHeader />

    <main className="flex-1 min-h-0 px-6 pb-5 pt-1 flex flex-col gap-3">
      {/* Top row: profile | calendar | featured trip */}
      <div className="flex gap-3 flex-[5] min-h-0">
        <div className="w-[22%]">
          <UserProfileCard
            name="Vignesh"
            milesLabel="140 Miles Traveled"
            image="https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=400&q=80"
          />
        </div>
        <div className="flex-1">
          <CalendarWidget year={2025} />
        </div>
        <div className="w-[36%]">
          <FeaturedDestinationCard
            city="PARIS, FRANCE"
            dates="28 Jul – 26 Jul"
            price="$864"
            nights="2 nights"
            destinations="1 destination"
            members={["Vignesh", "Arjun"]}
          />
        </div>
      </div>

      {/* Bottom row: previous trips | map */}
      <div className="flex gap-3 flex-[6] min-h-0">
        <div className="w-[30%]">
          <PreviousTrips />
        </div>
        <div className="flex-1">
          <EuropeMap />
        </div>
      </div>
    </main>
  </div>
)

export default Home
