// Shared rule for showing how fresh information is (passenger app and dashboard).
// Never show old queue/seat numbers as if they were live.

export const STALE_AFTER_MIN = 10;
export const UNAVAILABLE_AFTER_MIN = 60;

function ago(mins) {
  if (mins < 60) return `${mins} min`;
  const h = Math.floor(mins / 60);
  return `${h} hr`;
}

export function freshness(lastUpdatedIso, now = Date.now()) {
  if (!lastUpdatedIso) return { level: "unavailable", label: "Information unavailable" };
  const mins = Math.floor((now - new Date(lastUpdatedIso).getTime()) / 60000);
  if (mins >= UNAVAILABLE_AFTER_MIN) return { level: "unavailable", label: "Information unavailable" };
  if (mins >= STALE_AFTER_MIN) {
    return { level: "stale", label: `Last updated ${ago(mins)} ago, may have changed` };
  }
  return { level: "fresh", label: mins < 1 ? "Updated just now" : `Updated ${ago(mins)} ago` };
}
