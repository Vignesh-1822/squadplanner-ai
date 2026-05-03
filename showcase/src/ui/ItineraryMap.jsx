import { useEffect, useMemo } from "react";
import L from "leaflet";
import { MapContainer, Marker, Polyline, Popup, TileLayer, ZoomControl, useMap } from "react-leaflet";
import { decodePolyline, coordsFromActivity } from "../utils/map.js";
import { titleize } from "../utils/format.js";

const DEFAULT_CENTER = [39.8283, -98.5795];

export function ItineraryMap({ day, destination }) {
  const stops = useMemo(() => stopsForDay(day), [day]);
  const positions = stops.map((stop) => stop.position).filter(Boolean);
  const routes = useMemo(() => routeLinesForDay(day, positions), [day, positions]);
  const center = positions[0] || destinationCenter(destination) || DEFAULT_CENTER;

  return (
    <div className="map-frame">
      <MapContainer
        center={center}
        zoom={12}
        zoomControl={false}
        scrollWheelZoom
        dragging
        touchZoom
        doubleClickZoom
        boxZoom
        keyboard
        wheelPxPerZoomLevel={55}
        className="leaflet-map"
      >
        <ZoomControl position="topright" />
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <EnableMapInteractions />
        <FitBounds markers={positions} fallback={center} />
        {routes.map((route, index) => (
          <Polyline key={`route-${index}`} positions={route} pathOptions={{ color: "#ef4444", weight: 4, opacity: 0.82 }} />
        ))}
        {stops.map((stop) => (
          <Marker icon={stopIcon(stop)} key={`${stop.kind}-${stop.order}-${stop.label}`} position={stop.position}>
            <Popup>
              <strong>
                {stop.order}. {stop.label}
              </strong>
              <br />
              {titleize(stop.kind)}
              {stop.time ? (
                <>
                  <br />
                  Time: {stop.time}
                </>
              ) : null}
              {stop.address ? (
                <>
                  <br />
                  {stop.address}
                </>
              ) : null}
            </Popup>
          </Marker>
        ))}
      </MapContainer>
    </div>
  );
}

function EnableMapInteractions() {
  const map = useMap();

  useEffect(() => {
    map.scrollWheelZoom.enable();
    map.dragging.enable();
    map.touchZoom.enable();
    map.doubleClickZoom.enable();
    map.boxZoom.enable();
    map.keyboard.enable();
    map.invalidateSize();
  }, [map]);

  return null;
}

function FitBounds({ markers, fallback }) {
  const map = useMap();

  useEffect(() => {
    window.setTimeout(() => map.invalidateSize(), 80);
    if (markers.length > 1) {
      map.fitBounds(markers, { padding: [48, 48], maxZoom: 14 });
    } else {
      map.setView(markers[0] || fallback, markers.length ? 13 : 4);
    }
  }, [fallback, map, markers]);

  return null;
}

function stopsForDay(day) {
  if (Array.isArray(day?.route_stops) && day.route_stops.length) {
    return [...day.route_stops]
      .filter((stop) => stop.lat !== undefined && stop.lng !== undefined)
      .sort((a, b) => Number(a.order || 0) - Number(b.order || 0))
      .map((stop, index) => ({
        order: Number(stop.order || index + 1),
        kind: stop.type || "activity",
        label: stop.label || "Stop",
        time: stop.time,
        address: stop.address,
        position: [Number(stop.lat), Number(stop.lng)],
      }));
  }

  return (day?.activities || [])
    .map((activity, index) => {
      const position = coordsFromActivity(activity);
      if (!position) return null;
      return {
        order: index + 1,
        kind: "activity",
        label: activity.name,
        time: null,
        address: activity.address,
        position,
      };
    })
    .filter(Boolean);
}

function routeLinesForDay(day, positions) {
  const decodedRoutes = (day?.routes || [])
    .map((route) => decodePolyline(route?.polyline || route?.encodedPolyline || ""))
    .filter((line) => line.length > 1);

  if (decodedRoutes.length) return decodedRoutes;
  return positions.length > 1 ? [positions] : [];
}

function stopIcon(stop) {
  const config = {
    hotel: { className: "map-stop hotel", symbol: "H" },
    restaurant: { className: "map-stop restaurant", symbol: "R" },
    activity: { className: "map-stop activity", symbol: "A" },
  }[stop.kind] || { className: "map-stop activity", symbol: "A" };

  return L.divIcon({
    className: "",
    html: `<span class="${config.className}"><b>${stop.order}</b><em>${config.symbol}</em></span>`,
    iconSize: [38, 38],
    iconAnchor: [19, 19],
    popupAnchor: [0, -18],
  });
}

function destinationCenter(destination) {
  const lat = Number(destination?.lat ?? destination?.latitude);
  const lng = Number(destination?.lng ?? destination?.longitude);
  return Number.isFinite(lat) && Number.isFinite(lng) ? [lat, lng] : null;
}
