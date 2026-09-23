/**
 * Decode Google's encoded polyline format.
 *
 * `routes[].polyline` comes from the Google Routes API and describes the actual street-level
 * path between two stops, not a straight line — so the map can draw the walk people will really
 * take. Ported from showcase/src/utils/map.js rather than adding a dependency for ~30 lines.
 */
export function decodePolyline(encoded = "") {
  const coordinates = []
  let index = 0
  let lat = 0
  let lng = 0

  while (index < encoded.length) {
    const latChunk = decodeChunk(encoded, index)
    index = latChunk.index
    lat += latChunk.delta

    const lngChunk = decodeChunk(encoded, index)
    index = lngChunk.index
    lng += lngChunk.delta

    coordinates.push([lat / 1e5, lng / 1e5])
  }

  return coordinates
}

function decodeChunk(encoded, startIndex) {
  let result = 0
  let shift = 0
  let index = startIndex
  let byte = null

  do {
    byte = encoded.charCodeAt(index) - 63
    index += 1
    result |= (byte & 0x1f) << shift
    shift += 5
  } while (byte >= 0x20 && index < encoded.length)

  return { index, delta: result & 1 ? ~(result >> 1) : result >> 1 }
}
