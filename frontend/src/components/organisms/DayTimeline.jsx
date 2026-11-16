import { Fragment } from "react"
import TimelineItem from "@/molecules/TimelineItem"
import TransitConnector from "@/molecules/TransitConnector"
import { dayTimeline } from "@/lib/itinerary"

/** The day's stops in order, with the travel between them drawn in the gaps. */
const DayTimeline = ({ day }) => {
  const items = dayTimeline(day)

  if (!items.length) {
    return (
      <p className="text-slate-400 text-sm font-medium py-8 text-center">
        No schedule was produced for this day.
      </p>
    )
  }

  return (
    <div className="space-y-1">
      {items.map((item, index) => (
        <Fragment key={item.key}>
          <TimelineItem item={item} />
          {index < items.length - 1 && <TransitConnector leg={item.leg} />}
        </Fragment>
      ))}
    </div>
  )
}

export default DayTimeline
