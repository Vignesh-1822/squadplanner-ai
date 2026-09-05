import { apiFetch, BASE_URL } from "@/services"

/* auth */
export const getMe        = ()     => apiFetch("/auth/me")
export const register     = (data) => apiFetch("/auth/register", { method: "POST", body: JSON.stringify(data) })
export const login        = (data) => apiFetch("/auth/login",    { method: "POST", body: JSON.stringify(data) })
export const googleAuth   = (data) => apiFetch("/auth/google",   { method: "POST", body: JSON.stringify(data) })
export const logout       = ()     => apiFetch("/auth/logout",   { method: "POST" })

/* trips */
export const getTrips    = (email) => apiFetch(email ? `/trips?email=${email}` : "/trips")
export const getTripById = (id)    => apiFetch(`/trips/${id}`)
export const createTrip  = (data)  => apiFetch("/trips", { method: "POST", body: JSON.stringify(data) })

/* squad */
export const getTripByInvite  = (code)     => apiFetch(`/trips/by-invite/${code}`)
export const joinTrip         = (id)       => apiFetch(`/trips/${id}/join`, { method: "POST" })
export const submitPreferences = (id, data) =>
  apiFetch(`/trips/${id}/preferences`, { method: "POST", body: JSON.stringify(data) })
export const generateTrip     = (id, data = {}) =>
  apiFetch(`/trips/${id}/generate`, { method: "POST", body: JSON.stringify(data) })
// The email sits in the path, so it must be encoded — "+" and friends are legal in addresses.
export const removeMember     = (id, email) =>
  apiFetch(`/trips/${id}/members/${encodeURIComponent(email)}`, { method: "DELETE" })

/* planning */
export const confirmCity   = (id, data)   =>
  apiFetch(`/trips/${id}/confirm-city`, { method: "POST", body: JSON.stringify(data) })
export const getTripResult = (id)         => apiFetch(`/trips/${id}/result`)
export const refineTrip    = (id, message) =>
  apiFetch(`/trips/${id}/refine`, { method: "POST", body: JSON.stringify({ message }) })

/* SSE — EventSource cannot send headers, so auth must ride the cookie:
   new EventSource(streamUrl(id), { withCredentials: true }) */
export const streamUrl = (id) => `${BASE_URL}/trips/${id}/stream`
export const refinementStreamUrl = (id, refinementId) =>
  `${BASE_URL}/trips/${id}/refinements/${refinementId}/stream`
