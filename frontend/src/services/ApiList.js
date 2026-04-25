import { apiFetch } from "@/services"

export const getMe = () => apiFetch("/auth/me")

export const getTrips = () => apiFetch("/trips")
export const getTripById = (id) => apiFetch(`/trips/${id}`)
export const createTrip = (data) => apiFetch("/trips", { method: "POST", body: JSON.stringify(data) })
