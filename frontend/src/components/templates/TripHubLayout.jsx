import { Outlet, useParams, useNavigate } from "react-router-dom"
import { Toaster } from "sonner"
import { AlertTriangle, RefreshCw } from "lucide-react"
import HomeHeader from "@/organisms/HomeHeader"
import TripHero from "@/organisms/TripHero"
import TripTabs from "@/organisms/TripTabs"
import { useTripResult } from "@/hooks"

/**
 * Chrome shared by every trip-hub tab.
 *
 * The itinerary is fetched once here and handed down through the router outlet, so switching
 * tabs re-renders rather than refetches. Tabs read it with `useOutletContext()`.
 */
const TripHubLayout = () => {
  const { tripId } = useParams()
  const navigate = useNavigate()
  const { data, isLoading, error } = useTripResult(tripId)

  const shell = (children) => (
    <>
      <div
        className="min-h-screen font-sans flex flex-col"
        style={{
          background: `
            radial-gradient(ellipse at 4% 8%,  rgba(209,249,77,0.18) 0%, transparent 40%),
            radial-gradient(ellipse at 96% 6%,  rgba(255,182,200,0.22) 0%, transparent 38%),
            radial-gradient(ellipse at 55% 96%, rgba(200,220,255,0.14) 0%, transparent 45%),
            #f9f9f6
          `,
        }}
      >
        <HomeHeader />
        {children}
      </div>
      <Toaster position="top-right" richColors closeButton />
    </>
  )

  if (isLoading) {
    return shell(
      <div className="flex-1 flex items-center justify-center min-h-[60vh]">
        <div className="animate-pulse text-slate-500 font-medium">Loading your trip...</div>
      </div>,
    )
  }

  // GET /result answers 409 until a trip finishes, so this is the ordinary "not ready" path
  // as much as it is an error path.
  if (error || !data) {
    return shell(
      <main className="flex-1 flex items-center justify-center px-6 py-12">
        <div className="bg-white/60 backdrop-blur-xl rounded-[2rem] border border-white/70 shadow-sm p-12 text-center max-w-lg">
          <div className="size-14 rounded-full bg-amber-100 flex items-center justify-center mx-auto mb-5">
            <AlertTriangle size={26} className="text-amber-500" />
          </div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight mb-3">
            This trip isn&apos;t ready yet
          </h1>
          <p className="text-slate-500 text-sm font-medium mb-6">
            {error?.message || "The itinerary has not finished generating."}
          </p>
          <button
            type="button"
            onClick={() => navigate(`/trips/${tripId}/planning`)}
            className="inline-flex items-center gap-2 bg-slate-900 text-primary font-black text-xs uppercase tracking-widest px-6 py-3 rounded-xl hover:scale-[1.02] active:scale-95 transition-all cursor-pointer"
          >
            <RefreshCw size={14} />
            Check planning progress
          </button>
        </div>
      </main>,
    )
  }

  const itinerary = data.itinerary || {}

  return shell(
    <main className="flex-1 w-full max-w-6xl mx-auto px-4 md:px-8 pb-12 space-y-5">
      <TripHero
        tripName={data.trip_name}
        destination={itinerary.selected_destination}
        image={data.destination_image}
        startDate={itinerary.start_date}
        endDate={itinerary.end_date}
      />
      <TripTabs />
      <Outlet context={data} />
    </main>,
  )
}

export default TripHubLayout
