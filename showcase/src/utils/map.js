export function decodePolyline(encoded = "") {
  let index = 0;
  let lat = 0;
  let lng = 0;
  const coordinates = [];

  while (index < encoded.length) {
    const latResult = decodeChunk(encoded, index);
    index = latResult.index;
    lat += latResult.delta;

    const lngResult = decodeChunk(encoded, index);
    index = lngResult.index;
    lng += lngResult.delta;

    coordinates.push([lat / 1e5, lng / 1e5]);
  }

  return coordinates;
}

function decodeChunk(encoded, startIndex) {
  let result = 0;
  let shift = 0;
  let index = startIndex;
  let byte = null;

  do {
    byte = encoded.charCodeAt(index) - 63;
    index += 1;
    result |= (byte & 0x1f) << shift;
    shift += 5;
  } while (byte >= 0x20 && index < encoded.length);

  const delta = result & 1 ? ~(result >> 1) : result >> 1;
  return { delta, index };
}

export function coordsFromActivity(activity) {
  const lat = Number(activity?.lat ?? activity?.latitude);
  const lng = Number(activity?.lng ?? activity?.longitude);
  return Number.isFinite(lat) && Number.isFinite(lng) ? [lat, lng] : null;
}

export function routeLinesForDay(day) {
  const decodedRoutes = (day?.routes || [])
    .map((route) => decodePolyline(route?.polyline || route?.encodedPolyline || ""))
    .filter((line) => line.length > 1);

  if (decodedRoutes.length) return decodedRoutes;

  const fallback = (day?.activities || []).map(coordsFromActivity).filter(Boolean);
  return fallback.length > 1 ? [fallback] : [];
}
