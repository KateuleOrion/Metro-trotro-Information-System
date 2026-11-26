// Words shown to staff for the values the backend uses.
export const STATUS_LABELS = {
  available: "Available",
  queued: "In queue",
  loading: "Loading",
  departed: "Departed",
  unavailable: "Unavailable",
};

export const statusLabel = (status) => STATUS_LABELS[status] ?? "Unavailable";

export const PERIODS = [
  { value: "all", label: "All time" },
  { value: "today", label: "Today" },
  { value: "week", label: "Last 7 days" },
  { value: "month", label: "Last month" },
];

// Colours of the markers on the map, by direction of travel.
export const DIRECTION_COLORS = {
  approaching: "#1B6B45",
  arrived: "#1D4ED8",
  moving_away: "#B91C1C",
  stopped: "#6B7280",
  unknown: "#D97706",
  no_destination: "#6B7280",
};

// One plain sentence about where a vehicle is, for the map list and the marker label.
export function trackingText(v) {
  const dist = v.distance_km == null ? null : `${v.distance_km} km`;
  if (v.stale) {
    const mins = Math.round(v.age_minutes);
    return `No recent signal (last seen ${mins} minute${mins === 1 ? "" : "s"} ago)${dist ? `, ${dist} from ${v.destination}` : ""}`;
  }
  switch (v.direction) {
    case "approaching":
      return `Heading to ${v.destination}, ${dist} away` + (v.eta_minutes != null ? `, about ${v.eta_minutes} min` : "");
    case "arrived":
      return `Arrived at ${v.destination}`;
    case "moving_away":
      return `Moving away from ${v.destination}, ${dist} away`;
    case "stopped":
      return `Not moving, ${dist} from ${v.destination}`;
    case "no_destination":
      return `Location of ${v.destination ?? "the destination"} is not set yet`;
    default:
      return "Direction not known yet";
  }
}
