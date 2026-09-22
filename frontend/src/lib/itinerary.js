/**
 * Formatting helpers for the trip hub.
 *
 * Kept pure and separate from the components so the same rules apply wherever a day is drawn —
 * the timeline, the day banner and the sidebar summary all derive from the same numbers.
 */

/** Backend gives `price_level` 0–4, not an amount, so cards show a band rather than a price. */
export function priceLabel(priceLevel) {
  if (priceLevel === 0 || priceLevel === null || priceLevel === undefined) return "Free"
  return "$".repeat(Math.min(Math.max(priceLevel, 1), 4))
}

export function formatMoney(amount) {
  if (amount === null || amount === undefined) return "—"
  return `$${Math.round(Number(amount)).toLocaleString("en-US")}`
}

export function formatDayDate(iso) {
  if (!iso) return ""
  const date = new Date(`${iso}T00:00:00`)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" })
}

export function formatDateRange(start, end) {
  if (!start || !end) return "Dates TBD"
  const options = { month: "short", day: "numeric" }
  const from = new Date(`${start}T00:00:00`)
  const to = new Date(`${end}T00:00:00`)
  const year = to.getFullYear()
  return `${from.toLocaleDateString("en-US", options)} — ${to.toLocaleDateString("en-US", options)}, ${year}`
}

export function tripLengthDays(start, end) {
  if (!start || !end) return 0
  const from = new Date(`${start}T00:00:00`)
  const to = new Date(`${end}T00:00:00`)
  return Math.max(1, Math.round((to - from) / 86400000) + 1)
}

/** Total walking/driving distance for a day, summed from its route legs. */
export function dayDistanceKm(day) {
  const metres = (day?.routes || []).reduce((sum, leg) => sum + (leg.distance_meters || 0), 0)
  return metres ? (metres / 1000).toFixed(1) : null
}

export function formatDuration(seconds) {
  if (!seconds) return null
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes} min`
  const hours = Math.floor(minutes / 60)
  return `${hours}h ${minutes % 60}m`
}

const TRANSIT_VERB = { WALK: "walk", BICYCLE: "cycle", TRANSIT: "via transit", DRIVE: "drive" }

export function transitLabel(leg) {
  const duration = formatDuration(leg?.duration_seconds)
  if (!duration) return null
  const verb = TRANSIT_VERB[leg?.mode] || "travel"
  const distance = leg?.distance_meters ? ` · ${(leg.distance_meters / 1000).toFixed(1)} km` : ""
  return `${duration} ${verb}${distance}`
}

export function dayTitle(day) {
  const where = day?.neighborhood
  return where ? `Day ${day.day_number}: ${where}` : `Day ${day?.day_number ?? ""}`
}

/**
 * Weave the schedule and the activities into one ordered feed.
 *
 * `schedule` carries the clock times and meal stops; `activities` carries the place detail
 * (rating, address, tags). They are separate lists that describe the same day, so they are
 * matched by name where possible and the rest is passed through in schedule order.
 */
export function dayTimeline(day) {
  const activities = day?.activities || []
  const routes = day?.routes || []
  const meals = day?.meals || []
  const used = new Set()
  let activitiesSeen = 0

  return (day?.schedule || []).map((entry, index) => {
    const match = activities.find(
      (activity) =>
        !used.has(activity.place_id) &&
        (entry.label?.includes(activity.name) || entry.notes?.includes(activity.name)),
    )

    // Route legs connect consecutive *activities*, not consecutive schedule rows — a day can
    // hold six schedule entries and only two legs. Indexing by row would attribute a walk to
    // whichever meal happened to sit at that position.
    let leg = null
    if (match) {
      used.add(match.place_id)
      leg = routes[activitiesSeen] || null
      activitiesSeen += 1
    }

    // Meals name their venue in `meals` ("Dinner at L'Amour Bistro") but not in the schedule.
    const mealLabel =
      entry.type === "meal" ? meals.find((meal) => meal.startsWith(entry.label)) : null

    return {
      key: `${entry.time || index}-${entry.label || index}`,
      time: entry.time,
      type: entry.type,
      label: mealLabel || entry.label,
      notes: entry.notes,
      activity: match || null,
      leg,
    }
  })
}

/** Every mapped point for a day, in visit order. */
export function dayStops(day) {
  return (day?.activities || [])
    .filter((activity) => activity.lat && activity.lng)
    .map((activity, index) => ({
      order: index + 1,
      name: activity.name,
      lat: activity.lat,
      lng: activity.lng,
    }))
}

/** The five dimensions the agent scores, in the order the dataset defines them. */
export const PREFERENCE_DIMENSIONS = ["outdoor", "food", "nightlife", "urban", "shopping"]

const DIMENSION_LABEL = {
  outdoor: "Nature & Outdoors",
  food: "Food & Dining",
  nightlife: "Nightlife",
  urban: "Urban Exploration",
  shopping: "Shopping",
}

export const dimensionLabel = (key) => DIMENSION_LABEL[key] || key

/**
 * The squad's average taste, ranked.
 *
 * The result payload carries each member's own vector but not the group's, so it is averaged
 * here — the same mean the agent scores destinations with.
 */
export function groupPreferenceVector(members = []) {
  if (!members.length) return []

  return PREFERENCE_DIMENSIONS.map((key) => {
    const values = members
      .map((member) => Number(member?.preference_vector?.[key]))
      .filter((value) => Number.isFinite(value))
    const mean = values.length ? values.reduce((a, b) => a + b, 0) / values.length : 0
    return { key, label: dimensionLabel(key), value: mean }
  }).sort((a, b) => b.value - a.value)
}

/** What the trip is projected to cost, against what the squad said it could spend. */
export function tripSpend(itinerary) {
  const flights = (itinerary?.flights || []).reduce((sum, f) => sum + (f.price_usd || 0), 0)
  const hotel = itinerary?.hotel?.total_price_usd || 0
  const daily = (itinerary?.days || []).reduce((sum, d) => sum + (d.estimated_day_cost_usd || 0), 0)
  const budget = (itinerary?.members || []).reduce((sum, m) => sum + (m.budget_usd || 0), 0)
  const flightCount = (itinerary?.flights || []).length

  return {
    total: flights + hotel + daily,
    flights,
    hotel,
    daily,
    budget,
    averageFlight: flightCount ? flights / flightCount : 0,
  }
}

/**
 * Mirrors `_member_id_from_email` in backend/api/squad.py.
 *
 * Members are identified in the itinerary by an id derived from their email's local part, so
 * this is how the signed-in user is matched to their row. Collisions get a numeric suffix
 * server-side, hence the name fallback in `findMemberForUser`.
 */
export function memberIdFromEmail(email) {
  if (!email) return ""
  return email
    .split("@")[0]
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
}

/** The signed-in user's row in the itinerary, or null when they are not on this trip. */
export function findMemberForUser(members = [], user) {
  if (!user) return null
  const id = memberIdFromEmail(user.email)
  return (
    members.find((member) => member.member_id === id) ||
    members.find((member) => member.member_id?.startsWith(`${id}_`)) ||
    members.find((member) => member.name && member.name === user.name) ||
    null
  )
}

/**
 * What this trip costs one member.
 *
 * Scoped the same way the agent scores fairness: their flight plus an equal share of lodging.
 * Daily spend is shared and deliberately excluded, so this figure and `fairness_scores` agree.
 */
export function memberCostBreakdown(itinerary, member) {
  if (!member) return null

  const memberCount = Math.max((itinerary?.members || []).length, 1)
  const lodgingShare = (itinerary?.hotel?.total_price_usd || 0) / memberCount

  const prices = (itinerary?.flights || [])
    .filter((flight) => flight.member_id === member.member_id)
    .map((flight) => flight.price_usd || 0)
  const flight = prices.length ? Math.min(...prices) : 0

  const cost = flight + lodgingShare
  const budget = member.budget_usd || 0
  // The backend already computed this; prefer its number so the UI cannot disagree with the agent.
  const stored = itinerary?.fairness_scores?.[member.member_id]
  const utilisation = Number.isFinite(stored) ? stored : budget > 0 ? cost / budget : null

  return {
    flight,
    lodgingShare,
    cost,
    budget,
    utilisation,
    estimated: (itinerary?.flights || []).some(
      (f) => f.member_id === member.member_id && f.is_estimated,
    ),
  }
}

/**
 * The spread of budget utilisation across the squad.
 *
 * This — not an average — is what fairness measures: three members all at 60% is fair, while
 * one at 10% and one at 90% averages the same and is not. Lower utilisation is better.
 */
export function squadUtilisationRange(itinerary) {
  const values = Object.values(itinerary?.fairness_scores || {}).filter(Number.isFinite)
  if (!values.length) return null
  const min = Math.min(...values)
  const max = Math.max(...values)
  return {
    min: Math.round(min * 100),
    max: Math.round(max * 100),
    passed: itinerary?.fairness_passed !== false,
  }
}
