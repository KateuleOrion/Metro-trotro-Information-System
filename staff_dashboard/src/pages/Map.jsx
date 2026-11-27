import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { api } from "../api";
import LastUpdated from "../components/LastUpdated";
import { DIRECTION_COLORS, trackingText } from "../labels";

const REFRESH_SECONDS = 10; // the map refreshes by itself
const SHARE_EVERY_MS = 8000; // how often "share this device's location" sends a position
const ACCRA = [5.6037, -0.187];

// Marker labels are built as HTML, so text coming from the database is escaped first.
const escapeHtml = (text) =>
  String(text ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const dotIcon = (color, label, className = "") =>
  L.divIcon({
    className: "",
    html: `<div class="map-marker ${className}" style="--c:${color}"><span>${escapeHtml(label)}</span></div>`,
    iconSize: null,
  });

export default function MapPage({ user }) {
  const isManager = user?.role === "station_manager";
  const [tracked, setTracked] = useState([]);
  const [station, setStation] = useState(null);
  const [destinations, setDestinations] = useState([]);
  const [allVehicles, setAllVehicles] = useState([]);
  const [serverTime, setServerTime] = useState(null);
  const [pickedVehicle, setPickedVehicle] = useState("");
  const [mode, setMode] = useState(null); // { kind: "vehicle" | "destination", id, label } while waiting for a map click
  const [sharing, setSharing] = useState(null); // vehicle id whose position this device is sending
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const boxRef = useRef(null);
  const mapRef = useRef(null);
  const layerRef = useRef(null);
  const modeRef = useRef(null);
  const fittedRef = useRef(false);
  const watchRef = useRef(null);
  const lastSentRef = useRef(0);

  useEffect(() => {
    modeRef.current = mode; // the map's click handler reads the latest mode from here
  }, [mode]);

  async function load() {
    try {
      const [t, d, v] = await Promise.all([api.getTracking(), api.getDestinations(), api.getVehicles()]);
      setTracked(t.vehicles);
      setStation(t.station);
      setServerTime(t.server_time);
      setDestinations(d);
      setAllVehicles(v.vehicles);
      setError((e) => (e.startsWith("Cannot reach") ? "" : e));
    } catch (err) {
      setError(err.message);
    }
  }

  // Create the map once.
  useEffect(() => {
    const map = L.map(boxRef.current).setView(ACCRA, 11);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);
    layerRef.current = L.layerGroup().addTo(map);
    mapRef.current = map;

    map.on("click", async (e) => {
      const m = modeRef.current;
      if (!m) return;
      const { lat, lng } = e.latlng;
      try {
        if (m.kind === "vehicle") await api.reportPosition(m.id, lat, lng);
        else await api.setDestinationLocation(m.id, lat, lng);
        setNotice(m.kind === "vehicle" ? `Position of ${m.label} saved` : `Location of ${m.label} saved`);
        setError("");
      } catch (err) {
        setError(err.message);
      }
      setMode(null);
      load();
    });

    load();
    const timer = setInterval(load, REFRESH_SECONDS * 1000);
    return () => {
      clearInterval(timer);
      if (watchRef.current != null) navigator.geolocation.clearWatch(watchRef.current);
      map.remove();
    };
  }, []);

  // Redraw the markers whenever the data changes.
  useEffect(() => {
    const map = mapRef.current;
    const layer = layerRef.current;
    if (!map || !layer) return;
    layer.clearLayers();
    const points = [];

    if (station?.lat != null) {
      L.marker([station.lat, station.lon], { icon: dotIcon("#14201A", station.name, "station"), zIndexOffset: 100 }).addTo(layer);
      points.push([station.lat, station.lon]);
    }
    for (const d of destinations) {
      if (d.lat == null) continue;
      L.marker([d.lat, d.lon], { icon: dotIcon("#7C3AED", d.name, "destination") }).addTo(layer);
      points.push([d.lat, d.lon]);
    }
    for (const v of tracked) {
      const color = v.stale ? DIRECTION_COLORS.unknown : DIRECTION_COLORS[v.direction] ?? DIRECTION_COLORS.unknown;
      if (v.destination_lat != null) {
        L.polyline([[v.lat, v.lon], [v.destination_lat, v.destination_lon]], {
          color, weight: 2, opacity: 0.6, dashArray: "6 8",
        }).addTo(layer);
      }
      L.marker([v.lat, v.lon], { icon: dotIcon(color, v.plate_number, v.stale ? "stale" : ""), zIndexOffset: 1000 })
        .bindPopup(`<strong>${escapeHtml(v.plate_number)}</strong><br>${escapeHtml(trackingText(v))}`)
        .addTo(layer);
      points.push([v.lat, v.lon]);
    }
    // Zoom to everything once. After that the map stays where the staff member put it.
    if (!fittedRef.current && points.length > 1) {
      map.fitBounds(points, { padding: [40, 40], maxZoom: 14 });
      fittedRef.current = true;
    }
  }, [tracked, station, destinations]);

  function startPlacing() {
    const v = allVehicles.find((x) => String(x.id) === pickedVehicle);
    if (!v) return setError("Please select a vehicle");
    setError("");
    setNotice("");
    setMode({ kind: "vehicle", id: v.id, label: v.plate_number });
  }

  function startSettingDestination(d) {
    setError("");
    setNotice("");
    setMode({ kind: "destination", id: d.id, label: d.name });
  }

  function stopSharing() {
    if (watchRef.current != null) navigator.geolocation.clearWatch(watchRef.current);
    watchRef.current = null;
    setSharing(null);
  }

  function startSharing() {
    const v = allVehicles.find((x) => String(x.id) === pickedVehicle);
    if (!v) return setError("Please select a vehicle");
    if (!navigator.geolocation) return setError("This device cannot share its location");
    setError("");
    setNotice("");
    watchRef.current = navigator.geolocation.watchPosition(
      (pos) => {
        const nowMs = Date.now();
        if (nowMs - lastSentRef.current < SHARE_EVERY_MS) return;
        lastSentRef.current = nowMs;
        const kmh = pos.coords.speed != null ? Math.round(pos.coords.speed * 3.6 * 10) / 10 : null;
        api.reportPosition(v.id, pos.coords.latitude, pos.coords.longitude, kmh)
          .then(load)
          .catch((err) => setError(err.message));
      },
      (err) =>
        setError(
          err.code === 1
            ? "Location permission was refused. Allow location for this page in the browser settings"
            : "Could not get this device's location"
        ),
      { enableHighAccuracy: true, maximumAge: 5000 }
    );
    setSharing(v.id);
  }

  const order = { approaching: 0, arrived: 1, stopped: 2, moving_away: 3 };
  const sorted = [...tracked].sort((a, b) => (order[a.direction] ?? 9) - (order[b.direction] ?? 9));
  const missing = destinations.filter((d) => d.lat == null);
  const sharingVehicle = allVehicles.find((v) => v.id === sharing);

  return (
    <>
      {error && <p className="error" role="alert">{error}</p>}
      {notice && !error && <p className="notice" role="status">{notice}</p>}

      <div className="card">
        <h2>Update a position</h2>
        <form className="stack" onSubmit={(e) => e.preventDefault()}>
          <label>
            Vehicle
            <select value={pickedVehicle} onChange={(e) => setPickedVehicle(e.target.value)} disabled={!!sharing}>
              <option value="">{allVehicles.length ? "Select vehicle" : "No vehicles added yet"}</option>
              {allVehicles.map((v) => <option key={v.id} value={v.id}>{v.plate_number}</option>)}
            </select>
          </label>
          <button type="button" className="secondary" onClick={startPlacing} disabled={!!sharing}>
            Place it by tapping the map
          </button>
          {sharing ? (
            <button type="button" onClick={stopSharing}>Stop sharing this device's location</button>
          ) : (
            <button type="button" onClick={startSharing}>Share this device's location</button>
          )}
        </form>
        {sharing && (
          <p className="muted">
            Sending the location of this device as {sharingVehicle?.plate_number}. Keep this page open
            while sharing.
          </p>
        )}
        {isManager && missing.length > 0 && (
          <p className="actions">
            <span className="muted full">These destinations have no location yet, so no distance can be shown:</span>
            {missing.map((d) => (
              <button key={d.id} type="button" className="secondary small" onClick={() => startSettingDestination(d)}>
                Set location of {d.name}
              </button>
            ))}
          </p>
        )}
      </div>

      {mode && (
        <p className="notice" role="status">
          Tap the map to {mode.kind === "vehicle" ? `place ${mode.label}` : `set the location of ${mode.label}`}.{" "}
          <button type="button" className="secondary small" onClick={() => setMode(null)}>Cancel</button>
        </p>
      )}

      <div className="card">
        <div ref={boxRef} className={`map-box${mode ? " placing" : ""}`} />
        <p className="muted legend">
          <span><span className="dot" style={{ background: DIRECTION_COLORS.approaching }} />heading to destination</span>
          <span><span className="dot" style={{ background: DIRECTION_COLORS.moving_away }} />moving away</span>
          <span><span className="dot" style={{ background: DIRECTION_COLORS.stopped }} />not moving</span>
          <span><span className="dot" style={{ background: DIRECTION_COLORS.arrived }} />arrived</span>
          <span><span className="dot" style={{ background: DIRECTION_COLORS.unknown }} />no recent signal</span>
          <span><span className="dot" style={{ background: "#7C3AED" }} />destination</span>
        </p>
      </div>

      <h2>Vehicles on the road</h2>
      {sorted.length === 0 ? (
        <p className="empty">No vehicle has sent its position yet</p>
      ) : (
        <div className="list">
          {sorted.map((v) => (
            <div className="item" key={v.id}>
              <div className="item-head">
                <span className="dot" style={{ background: v.stale ? DIRECTION_COLORS.unknown : DIRECTION_COLORS[v.direction] }} />
                <span className="item-title">{v.plate_number}</span>
                <span className="chip grey">
                  {v.eta_minutes == null ? "No ETA" : v.eta_minutes === 0 ? "Arrived" : `~${v.eta_minutes} min`}
                </span>
              </div>
              <div className="item-sub">{trackingText(v)}</div>
              <dl className="facts">
                <dt>Route</dt><dd>{v.route_name ?? "Unavailable"}</dd>
                <dt>Distance</dt><dd>{v.distance_km == null ? "Unavailable" : `${v.distance_km} km`}</dd>
              </dl>
            </div>
          ))}
        </div>
      )}
      <p className="muted hint">
        Distances are in a straight line, so the real road distance is longer. The page refreshes every{" "}
        {REFRESH_SECONDS} seconds.
      </p>
      <LastUpdated value={serverTime} />
    </>
  );
}
