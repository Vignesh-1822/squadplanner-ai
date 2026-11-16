import { useQuery } from "@tanstack/react-query"
import { getTripResult } from "@/services/ApiList"

/**
 * The completed itinerary for a trip.
 *
 * Fetched once at the hub layout and shared with every tab through the router outlet, so
 * switching tabs is instant rather than a refetch. The payload is final once a trip completes,
 * hence the long stale time; a refinement invalidates this key explicitly.
 */
export function useTripResult(tripId) {
  return useQuery({
    queryKey: ["trip-result", tripId],
    queryFn: () => getTripResult(tripId),
    enabled: !!tripId,
    staleTime: 5 * 60 * 1000,
    retry: false, // a 409 means the trip has not finished; retrying will not change that
  })
}
