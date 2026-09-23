/**
 * Deep links into the user's own maps app, so they can actually get directions.
 *
 * Google gets the Places `place_id` where we have one — an exact venue match rather than a
 * coordinate that might resolve to the building next door. Apple Maps has no equivalent, so it
 * takes coordinates plus the name as a label.
 */

export function googleMapsDirections({ name, lat, lng, placeId }) {
  const params = new URLSearchParams({ api: "1" })
  params.set("destination", placeId ? name || `${lat},${lng}` : `${lat},${lng}`)
  if (placeId) params.set("destination_place_id", placeId)
  return `https://www.google.com/maps/dir/?${params.toString()}`
}

export function appleMapsDirections({ name, lat, lng }) {
  const params = new URLSearchParams({ daddr: `${lat},${lng}` })
  if (name) params.set("q", name)
  return `https://maps.apple.com/?${params.toString()}`
}

/** Apple platforms default to Apple Maps; both links are always offered either way. */
export const prefersAppleMaps = () =>
  typeof navigator !== "undefined" && /iPhone|iPad|iPod|Macintosh/.test(navigator.userAgent)
