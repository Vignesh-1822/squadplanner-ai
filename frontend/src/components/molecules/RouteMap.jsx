import { useMemo } from "react"
import { MapContainer, Marker, Polyline, Popup, TileLayer, Tooltip, useMap } from "react-leaflet"
import L from "leaflet"
import { Navigation } from "lucide-react"
import "leaflet/dist/leaflet.css"
import { decodePolyline } from "@/lib/polyline"
import { googleMapsDirections, appleMapsDirections, prefersAppleMaps } from "@/lib/mapLinks"

const PIN_W = 22
const PIN_H = 30

/**
 * Teardrop map pin, drawn as an inline-SVG divIcon.
 *
 * Leaflet's default marker resolves its PNGs by relative path, which bundlers break — a divIcon
 * sidesteps that and lets the visit number sit inside the pin head. Anchored at the tip so the
 * point, not the centre, marks the coordinate. Muted brick red rather than a signal red: the pin
 * should sit on the map, not shout over it.
 */
const pin = (order) =>
  L.divIcon({
    className: "",
    html: `
      <svg width="${PIN_W}" height="${PIN_H}" viewBox="0 0 22 30" xmlns="http://www.w3.org/2000/svg"
           style="filter:drop-shadow(0 1px 2px rgba(0,0,0,.28))">
        <path d="M11 0C4.9 0 0 4.9 0 11c0 8.2 11 19 11 19s11-10.8 11-19C22 4.9 17.1 0 11 0z"
              fill="#c0392b"/>
        <text x="11" y="10.5" text-anchor="middle" dominant-baseline="central"
              fill="#fff" font-size="11" font-weight="700"
              font-family="Inter, system-ui, sans-serif">${order}</text>
      </svg>`,
    iconSize: [PIN_W, PIN_H],
    iconAnchor: [PIN_W / 2, PIN_H],
    popupAnchor: [0, -PIN_H + 3],
    tooltipAnchor: [0, -PIN_H + 5],
  })

/** Keeps every stop of the day in frame whenever the day changes. */
const FitBounds = ({ points }) => {
  const map = useMap()
  useMemo(() => {
    if (points.length === 1) map.setView(points[0], 14)
    else if (points.length > 1) map.fitBounds(L.latLngBounds(points), { padding: [36, 36] })
  }, [map, points])
  return null
}

const RouteMap = ({ stops, legs, height = "11rem", interactive = false }) => {
  const points = stops.map((stop) => [stop.lat, stop.lng])
  const appleFirst = prefersAppleMaps()

  if (!points.length) return null

  return (
    <MapContainer
      center={points[0]}
      zoom={13}
      scrollWheelZoom={interactive}
      dragging={interactive}
      doubleClickZoom={interactive}
      zoomControl={interactive}
      attributionControl={interactive}
      style={{ height, width: "100%", background: "#e8eae4" }}
    >
      {/* OpenStreetMap standard: coloured and labelled, and the only genuinely keyless option —
          CARTO now watermarks anonymous tiles with "API KEY REQUIRED" across the whole image.
          No `{r}` placeholder: OSM has no retina tiles and 400s on an @2x request. */}
      <TileLayer
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
      />
      <FitBounds points={points} />

      {legs.map((leg) => {
        // The encoded polyline is the real street path; fall back to a straight line if the
        // routing call did not return one.
        const path = leg.polyline
          ? decodePolyline(leg.polyline)
          : [
              [leg.from.lat, leg.from.lng],
              [leg.to.lat, leg.to.lng],
            ]
        return (
          <Polyline
            key={leg.key}
            positions={path}
            pathOptions={{ color: "#afd528", weight: 4, opacity: 0.9 }}
          />
        )
      })}

      {stops.map((stop) => {
        const google = googleMapsDirections(stop)
        const apple = appleMapsDirections(stop)
        return (
          <Marker key={`${stop.order}-${stop.name}`} position={[stop.lat, stop.lng]} icon={pin(stop.order)}>
            {/* Hover names the stop; clicking opens the directions links below. */}
            <Tooltip direction="top" className="stop-name-label">
              {stop.name}
            </Tooltip>
            <Popup>
              <span className="block font-black text-slate-900 text-sm leading-tight mb-1">
                {stop.name}
              </span>
              {stop.address && (
                <span className="block text-slate-500 text-[11px] leading-snug mb-2">{stop.address}</span>
              )}
              <span className="flex items-center gap-2">
                <a
                  href={appleFirst ? apple : google}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="inline-flex items-center gap-1 font-bold text-[11px] text-slate-900 underline"
                >
                  <Navigation size={11} />
                  {appleFirst ? "Apple Maps" : "Google Maps"}
                </a>
                <a
                  href={appleFirst ? google : apple}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="font-bold text-[11px] text-slate-500 underline"
                >
                  {appleFirst ? "Google Maps" : "Apple Maps"}
                </a>
              </span>
            </Popup>
          </Marker>
        )
      })}
    </MapContainer>
  )
}

export default RouteMap
