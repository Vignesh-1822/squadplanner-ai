/**
 * Builds the member payload the planning agent expects.
 *
 * The backend's `preference_vector` uses exactly five keys, taken from the `vibe_tags`
 * in backend/data/destinations.json, and scores them 0.0–1.0. The sliders in the UI run
 * 0–100, so everything is normalized here rather than at each call site.
 */

export const PREFERENCE_KEYS = ["outdoor", "food", "nightlife", "urban", "shopping"]

export const DIETARY_OPTIONS = [
  { key: "vegetarian", label: "Vegetarian" },
  { key: "vegan", label: "Vegan" },
  { key: "gluten-free", label: "Gluten-free" },
  { key: "halal", label: "Halal" },
]

const SLIDER_MAX = 100

/** Turn the slider list into the backend's 0.0–1.0 keyed vector. */
export function normalizePreferenceVector(vibes) {
  return vibes.reduce((vector, { key, value }) => {
    vector[key] = value / SLIDER_MAX
    return vector
  }, {})
}

/**
 * The backend has no field for carry-on, so it rides along in the notes the
 * constraint extractor already reads as free text.
 */
export function buildPreferenceNotes(notes, { carryOnOnly }) {
  const parts = []
  const trimmed = notes?.trim()
  if (trimmed) parts.push(trimmed)
  if (carryOnOnly) parts.push("Carry-on luggage only.")
  return parts.join(" ")
}

/** Drop half-filled rows — a window is only usable once both ends are set. */
export function usableDateWindows(dateWindows) {
  return dateWindows
    .filter((window) => window.start_date && window.end_date)
    .map(({ start_date, end_date }) => ({ start_date, end_date }))
}

export function buildMemberPayload({
  user,
  isLeader = false,
  vibes,
  airport,
  budget,
  carryOn,
  dietary,
  notes,
  dateWindows,
}) {
  return {
    member_id: user?.id ?? "",
    name: user?.name ?? "",
    origin_city: airport,
    budget_usd: Number(budget),
    food_restrictions: dietary,
    preference_vector: normalizePreferenceVector(vibes),
    preference_notes: buildPreferenceNotes(notes, { carryOnOnly: carryOn }),
    // The agent plans one date range for the whole trip; the squad's windows are
    // reconciled at start-planning time, so every window is carried through here.
    availability: usableDateWindows(dateWindows),
    is_leader: isLeader,
  }
}
