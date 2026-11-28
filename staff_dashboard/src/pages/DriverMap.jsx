import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { api } from "../api";
import LastUpdated from "../components/LastUpdated";
import { DIRECTION_COLORS, trackingText } from "../labels";

// The driver's map: where their vehicle is, the station and the destination, how far and how long.
// This map has no live traffic, so "Directions with live traffic" opens Google Maps for the route.
const REFRESH_SECONDS = 10;
const SHARE_EVERY_MS = 8000; // how often a shared location is sent
const ACCRA = [5.6037, -0.187];

const escapeHtml = (text) =>
  String(text ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const dotIcon = (color, label, className = "") =>
  L.divIcon({
    className: "",
    html: `<div class="map-marker ${className}" style="--c:${color}"><span>${escapeHtml(label)}</span></div>`,
    iconSize: null,
  });

// Google Maps directions link: shows live traffic and faster routes. No API key needed.
function directionsUrl(v) {
  const m = v.map;
  const destination = m.destination_lat != null ? `${m.destination_lat},${m.destination_lon}` : `${m.destination}, Ghana`;
  const origin = m.lat != null && !m.stale ? `&origin=${m.lat},${m.lon}` : ""; // otherwise Google uses the phone's location
  return `https://www.google.com/maps/dir/?api=1${origin}&destination=${encodeURIComponent(destination)}&travelmode=driving`;
}

export default function DriverMap() {
  const [me, setMe] = useState(null);
  const [vehicleId, setVehicleId] = useState("");
  const [sharing, setSharing] = useState(false);
  const [error, setError] = useState("");
  const mapBox = useRef(null);
  const mapRef = useRef(null);
  const layerRef = useRef(null);
  const watchRef = useRef(null);
  const lastSentRef = useRef(0);
  const fittedRef = useRef(false);

  async function load() {
    try {
      setMe(await api.getDriverMe());
      setError((e) => (e.startsWith("Location") || e.startsWith("Could not") ? e : ""));
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    const map = L.map(mapBox.current, { zoomControl: true }).setView(ACCRA, 12);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap contributors",
    }).addTo(map);
    mapRef.current = map;
    layerRef.current = L.layerGroup().addTo(map);
    load();
    const timer = setInterval(load, REFRESH_SECONDS * 1000);
    return () => {
      clearInterval(timer);
      if (watchRef.current != null) navigator.geolocation.clearWatch(watchRef.current);
      map.remove();
    };
  }, []);

  const vehicles = me?.vehicles ?? [];
  const vehicle = vehicles.find((v) => String(v.id) === vehicleId) ?? vehicles[0] ?? null;

  // Redraw the markers whenever the data changes.
  useEffect(() => {
    const map = mapRef.current;
    const layer = layerRef.current;
    if (!map || !layer) return;
    layer.clearLayers();
    const points = [];
    const st = me?.station;
    if (st?.lat != null) {
      L.marker([st.lat, st.lon], { icon: dotIcon("#14201A", st.name, "station") }).addTo(layer);
      points.push([st.lat, st.lon]);
    }
    if (vehicle) {
      const m = vehicle.map;
      if (m.destination_lat != null) {
        L.marker([m.destination_lat, m.destination_lon], { icon: dotIcon("#7C3AED", m.destination, "destination") }).addTo(layer);
        points.push([m.destination_lat, m.destination_lon]);
      }
      if (m.lat != null) {
        if (m.destination_lat != null) {
          L.polyline([[m.lat, m.lon], [m.destination_lat, m.destination_lon]], {
            color: "#7C3AED", weight: 3, dashArray: "6 6", opacity: 0.8,
          }).addTo(layer);
        }
        const color = m.stale ? DIRECTION_COLORS.unknown : DIRECTION_COLORS[m.direction] ?? DIRECTION_COLORS.unknown;
        L.marker([m.lat, m.lon], { icon: dotIcon(color, vehicle.plate_number, m.stale ? "stale" : ""), zIndexOffset: 1000 })
          .addTo(layer);
        points.push([m.lat, m.lon]);
      }
    }
    if (points.length && !fittedRef.current) {
      map.fitBounds(points, { padding: [30, 30], maxZoom: 14 });
      fittedRef.current = true;
    }
  }, [me, vehicle]);

  function stopSharing() {
    if (watchRef.current != null) navigator.geolocation.clearWatch(watchRef.current);
    watchRef.current = null;
    setSharing(false);
  }

  function startSharing() {
    if (!vehicle) return;
    if (!navigator.geolocation) return setError("Could not get this phone's location");
    setError("");
    watchRef.current = navigator.geolocation.watchPosition(
      (pos) => {
        if (Date.now() - lastSentRef.current < SHARE_EVERY_MS) return;
        lastSentRef.current = Date.now();
        const kmh = pos.coords.speed != null ? Math.round(pos.coords.speed * 3.6 * 10) / 10 : null;
        api.reportPosition(vehicle.id, pos.coords.latitude, pos.coords.longitude, kmh)
          .then(load)
          .catch((err) => setError(err.message));
      },
      (err) =>
        setError(err.code === 1
          ? "Location permission was refused. Allow location for this page in the browser settings"
          : "Could not get this phone's location"),
      { enableHighAccuracy: true, maximumAge: 5000 }
    );
    setSharing(true);
  }

  const m = vehicle?.map;

  return (
    <>
      {error && <p className="error" role="alert">{error}</p>}

      {vehicles.length > 1 && (
        <div className="card">
          <label>
            Your vehicle
            <select value={vehicle ? String(vehicle.id) : ""}
              onChange={(e) => { setVehicleId(e.target.value); fittedRef.current = false; }}>
              {vehicles.map((v) => <option key={v.id} value={v.id}>{v.plate_number}</option>)}
            </select>
          </label>
        </div>
      )}

      {me && !vehicle && <p className="empty">No vehicle is linked to you yet. Please ask the station manager.</p>}

      {vehicle && (
        <div className="card">
          <div className="item-head">
            <span className="item-title">{vehicle.plate_number}</span>
            <span className="chip grey">
              {m.eta_minutes == null ? "No ETA" : m.eta_minutes === 0 ? "Arrived" : `~${m.eta_minutes} min`}
            </span>
          </div>
          <div className="item-sub">
            {m.lat == null ? `To ${m.destination}. Share your location to see where you are.` : trackingText(m)}
          </div>
        </div>
      )}

      <div ref={mapBox} className="map-box driver-map" />

      {vehicle && (
        <div className="actions">
          <a className="button full" href={directionsUrl(vehicle)} target="_blank" rel="noreferrer">
            Directions with live traffic
          </a>
          {sharing ? (
            <button className="secondary full" onClick={stopSharing}>Stop sharing my location</button>
          ) : (
            <button className="secondary full" onClick={startSharing}>Share my location</button>
          )}
        </div>
      )}
      <p className="hint center">Directions open in Google Maps, which shows live traffic and faster routes.</p>
      <LastUpdated value={me?.last_updated} />
    </>
  );
}
