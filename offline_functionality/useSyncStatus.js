import { useEffect, useState } from "react";
import { liveQuery } from "dexie";
import { countByStatus } from "./outbox";

// React hook for the dashboard: online/offline plus how many records are waiting.
export function useSyncStatus() {
  const [counts, setCounts] = useState({ pending: 0, failed: 0, synced: 0 });
  const [online, setOnline] = useState(navigator.onLine);

  useEffect(() => {
    const sub = liveQuery(() => countByStatus()).subscribe({ next: setCounts });
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => {
      sub.unsubscribe();
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, []);

  return { online, counts, waiting: counts.pending + counts.failed };
}
