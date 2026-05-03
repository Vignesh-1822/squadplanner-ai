export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(
  /\/$/,
  "",
);

async function readJson(response) {
  const text = await response.text();
  const payload = text ? JSON.parse(text) : {};
  if (!response.ok) {
    const message = payload?.detail || payload?.message || response.statusText;
    throw new Error(message);
  }
  return payload;
}

function networkErrorMessage(action) {
  return `${action} failed because the backend is not reachable at ${API_BASE_URL}. Start the FastAPI backend locally or set VITE_API_BASE_URL to your hosted API URL.`;
}

export async function createTrip(payload) {
  try {
    const response = await fetch(`${API_BASE_URL}/trips`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return readJson(response);
  } catch (error) {
    if (error instanceof TypeError) throw new Error(networkErrorMessage("Trip creation"));
    throw error;
  }
}

export async function confirmCity(tripId, destination) {
  const coords = getCandidateCoords(destination);
  try {
    const response = await fetch(`${API_BASE_URL}/trips/${tripId}/confirm-city`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        selected_destination: destination.name || destination.destination || "Selected destination",
        selected_destination_coords: coords,
      }),
    });
    return readJson(response);
  } catch (error) {
    if (error instanceof TypeError) throw new Error(networkErrorMessage("Destination confirmation"));
    throw error;
  }
}

export async function getTrip(tripId) {
  try {
    const response = await fetch(`${API_BASE_URL}/trips/${tripId}`);
    return readJson(response);
  } catch (error) {
    if (error instanceof TypeError) throw new Error(networkErrorMessage("Trip loading"));
    throw error;
  }
}

export function streamUrl(tripId) {
  return `${API_BASE_URL}/trips/${tripId}/stream`;
}

export function getCandidateCoords(candidate) {
  const coords = candidate?.coords || candidate?.coordinates || candidate?.selected_destination_coords || candidate;
  return {
    lat: Number(coords?.lat ?? coords?.latitude ?? 0),
    lng: Number(coords?.lng ?? coords?.longitude ?? 0),
  };
}
