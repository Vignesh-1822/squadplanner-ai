const PREFIX = "squadplanner-showcase";

export function saveTripPayload(tripId, payload) {
  localStorage.setItem(`${PREFIX}:trip:${tripId}`, JSON.stringify(payload));
}

export function loadTripPayload(tripId) {
  const raw = localStorage.getItem(`${PREFIX}:trip:${tripId}`);
  return raw ? JSON.parse(raw) : null;
}
