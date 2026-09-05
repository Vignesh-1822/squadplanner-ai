/**
 * The status vocabulary, straight from the backend.
 *
 *   Trip:   pending -> collecting -> generating -> city_selection -> complete
 *   Member: pending -> joined -> ready
 *
 * The UI used to check for "accepted", which the backend never emits — so every member
 * read as "Invitation Sent" forever and readiness sat at zero. Keeping the vocabulary in
 * one module stops that drifting again. See docs/FRONTEND_CONTRACT.md.
 */

export const MEMBER_PENDING = "pending"
export const MEMBER_JOINED = "joined"
export const MEMBER_READY = "ready"

export const isCollecting = (status) => status === "pending" || status === "collecting"
export const isPlanning = (status) => status === "generating" || status === "city_selection"
export const isComplete = (status) => status === "complete"

export const isMemberReady = (member) => member?.status === MEMBER_READY

/**
 * Poll fast only when something is about to happen.
 *
 * A lobby spends most of its life waiting on humans, so 30s is plenty. Once everyone is
 * ready the leader is about to press the button, and every other member needs to notice
 * quickly — that is the one window worth polling hard. Past that the lobby is done.
 */
export function lobbyRefetchInterval(trip) {
  if (!trip) return 5000
  if (isPlanning(trip.status) || isComplete(trip.status)) return false
  return trip.all_ready ? 5000 : 30000
}
