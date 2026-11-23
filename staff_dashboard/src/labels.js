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
