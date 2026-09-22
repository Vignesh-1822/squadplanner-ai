import { MapPin, CalendarDays, Share2 } from "lucide-react"
import { formatDateRange, tripLengthDays } from "@/lib/itinerary"
import { toast } from "sonner"

/** The banner across the top of every hub tab: where, when, and a photo of it. */
const TripHero = ({ tripName, destination, image, startDate, endDate }) => {
  const nights = tripLengthDays(startDate, endDate)

  const share = () => {
    navigator.clipboard.writeText(window.location.href)
    toast.success("Trip link copied to clipboard!")
  }

  return (
    <section className="relative overflow-hidden rounded-[2rem] bg-gradient-to-br from-slate-800 via-slate-700 to-slate-900 min-h-[250px] md:min-h-[260px] flex items-end">
      {image?.image_url && (
        <img
          src={image.image_url}
          alt={destination || tripName}
          className="absolute inset-0 w-full h-full object-cover"
        />
      )}
      {/* Keeps the title legible whatever the photo turns out to be */}
      <div className="absolute inset-0 bg-gradient-to-t from-slate-950/85 via-slate-950/40 to-slate-950/20" />

      <div className="relative z-10 w-full p-6 md:p-8 flex flex-wrap items-end justify-between gap-4">
        <div className="space-y-2">
          {destination && (
            <span className="inline-flex items-center gap-1.5 text-primary text-[10px] font-black uppercase tracking-[0.2em]">
              <MapPin size={12} />
              {destination}
            </span>
          )}
          <h1 className="text-3xl md:text-5xl font-black text-white tracking-tight leading-none">
            {tripName || destination || "Your trip"}
          </h1>
          <p className="flex items-center gap-2 text-white/70 text-sm font-medium">
            <CalendarDays size={14} />
            {formatDateRange(startDate, endDate)}
            {nights > 0 && <span className="text-white/40">• {nights} days</span>}
          </p>
        </div>

        <button
          type="button"
          onClick={share}
          className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-white/15 backdrop-blur-md border border-white/25 text-white text-xs font-bold uppercase tracking-widest hover:bg-white/25 transition-colors cursor-pointer"
        >
          <Share2 size={14} />
          Share
        </button>
      </div>

      {image?.image_credit && (
        <a
          href={image.image_link || undefined}
          target="_blank"
          rel="noreferrer noopener"
          className="absolute bottom-2 right-3 z-10 text-[10px] text-white/50 hover:text-white/80 transition-colors"
        >
          {image.image_credit} / {image.image_source}
        </a>
      )}
    </section>
  )
}

export default TripHero
