import { useEffect, useState } from "react";
import { api } from "../api";
import { ROLE_LABELS } from "../labels";

// Station manager only: drivers who asked to be registered. Approving creates the driver
// (and their vehicle, if they gave one). Rejecting keeps a reason the driver can see.
const TABS = [
  { value: "pending", label: "Waiting" },
  { value: "approved", label: "Approved" },
  { value: "rejected", label: "Rejected" },
];

const when = (iso) => (iso ? new Date(iso).toLocaleString([], { dateStyle: "medium", timeStyle: "short" }) : "");

function DriverRequests() {
  const [tab, setTab] = useState("pending");
  const [requests, setRequests] = useState([]);
  const [loaded, setLoaded] = useState(false);
  const [rejecting, setRejecting] = useState(null); // request id whose reject box is open
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function load(which = tab) {
    try {
      setRequests(await api.getDriverRequests(which));
      setLoaded(true);
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    load(tab);
  }, [tab]);

  async function review(r, action) {
    setBusy(r.id);
    try {
      if (action === "approve") {
        await api.approveDriverRequest(r.id);
        setNotice(r.plate ? `${r.name} and vehicle ${r.plate} are now registered` : `${r.name} is now registered`);
      } else {
        await api.rejectDriverRequest(r.id, reason.trim());
        setNotice(`Request from ${r.name} rejected`);
      }
      setError("");
      setRejecting(null);
      setReason("");
      window.dispatchEvent(new Event("driver-requests-changed")); // updates the count on the tab bar
    } catch (err) {
      setError(err.message);
      setNotice("");
    }
    setBusy(null);
    load();
  }

  return (
    <>
      <div className="segments" role="tablist" aria-label="Request status">
        {TABS.map((t) => (
          <button key={t.value} role="tab" aria-selected={tab === t.value} className={tab === t.value ? "on" : ""}
            onClick={() => { setLoaded(false); setTab(t.value); setNotice(""); setError(""); }}>
            {t.label}
          </button>
        ))}
      </div>

      {error && <p className="error" role="alert">{error}</p>}
      {notice && !error && <p className="notice" role="status">{notice}</p>}

      {loaded && requests.length === 0 && (
        <p className="empty">
          {tab === "pending" ? "No driver requests waiting" : `No ${tab} requests`}
        </p>
      )}

      <div className="list">
        {requests.map((r) => (
          <div className="item" key={r.id}>
            <div className="item-head">
              <span className="item-title">{r.name}</span>
              <span className={`chip ${r.status}`}>{TABS.find((t) => t.value === r.status)?.label}</span>
            </div>
            <div className="item-sub">Sent {when(r.submitted_at)}</div>
            <dl className="facts">
              <dt>Phone</dt><dd><a href={`tel:${r.phone.replace(/\s/g, "")}`}>{r.phone}</a></dd>
              {r.plate ? (
                <>
                  <dt>Vehicle</dt><dd>{r.plate}</dd>
                  <dt>Destination</dt><dd>{r.destination}</dd>
                  <dt>Seats</dt><dd>{r.seats}</dd>
                </>
              ) : (
                <><dt>Vehicle</dt><dd className="muted">None given</dd></>
              )}
              {r.status !== "pending" && (
                <><dt>{r.status === "approved" ? "Approved" : "Rejected"}</dt><dd>{when(r.reviewed_at)}{r.reviewed_by ? ` by ${r.reviewed_by}` : ""}</dd></>
              )}
              {r.reason && <><dt>Reason</dt><dd>{r.reason}</dd></>}
            </dl>

            {r.status === "pending" && rejecting !== r.id && (
              <div className="actions">
                <button className="danger" disabled={busy === r.id}
                  onClick={() => { setRejecting(r.id); setReason(""); }}>Reject</button>
                <button disabled={busy === r.id} onClick={() => review(r, "approve")}>
                  {busy === r.id ? "Saving..." : "Approve"}
                </button>
              </div>
            )}

            {r.status === "pending" && rejecting === r.id && (
              <div className="stack" style={{ marginTop: 12 }}>
                <label>
                  Reason (the driver will see this)
                  <textarea value={reason} maxLength={255} onChange={(e) => setReason(e.target.value)}
                    placeholder="e.g. Please bring your vehicle papers to the station office" />
                </label>
                <div className="actions">
                  <button className="secondary" onClick={() => setRejecting(null)}>Cancel</button>
                  <button className="danger" disabled={busy === r.id} onClick={() => review(r, "reject")}>
                    Confirm reject
                  </button>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </>
  );
}


// ---------------------------------------------------------------- new station staff / manager accounts
const STAFF_TABS = [
  { value: "pending", label: "Waiting" },
  { value: "active", label: "Approved" },
  { value: "rejected", label: "Rejected" },
];

function StaffAccounts() {
  const [tab, setTab] = useState("pending");
  const [accounts, setAccounts] = useState([]);
  const [loaded, setLoaded] = useState(false);
  const [rejecting, setRejecting] = useState(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function load(which = tab) {
    try {
      setAccounts(await api.getStaffAccounts(which));
      setLoaded(true);
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    load(tab);
  }, [tab]);

  async function review(a, action) {
    setBusy(a.id);
    try {
      if (action === "approve") {
        await api.approveStaffAccount(a.id);
        setNotice(`${a.name} can now log in (${ROLE_LABELS[a.role]})`);
      } else {
        await api.rejectStaffAccount(a.id, reason.trim());
        setNotice(`Account for ${a.name} rejected`);
      }
      setError("");
      setRejecting(null);
      setReason("");
      window.dispatchEvent(new Event("driver-requests-changed")); // updates the count on the tab bar
    } catch (err) {
      setError(err.message);
      setNotice("");
    }
    setBusy(null);
    load();
  }

  return (
    <>
      <div className="segments" role="tablist" aria-label="Account status">
        {STAFF_TABS.map((t) => (
          <button key={t.value} role="tab" aria-selected={tab === t.value} className={tab === t.value ? "on" : ""}
            onClick={() => { setLoaded(false); setTab(t.value); setNotice(""); setError(""); }}>
            {t.label}
          </button>
        ))}
      </div>

      {error && <p className="error" role="alert">{error}</p>}
      {notice && !error && <p className="notice" role="status">{notice}</p>}

      {loaded && accounts.length === 0 && (
        <p className="empty">{tab === "pending" ? "No new accounts waiting" : "None yet"}</p>
      )}

      <div className="list">
        {accounts.map((a) => (
          <div className="item" key={a.id}>
            <div className="item-head">
              <span className="item-title">{a.name}</span>
              <span className={`chip ${a.status}`}>{STAFF_TABS.find((t) => t.value === a.status)?.label}</span>
            </div>
            <div className="item-sub">Registered {when(a.created_at)}</div>
            <dl className="facts">
              <dt>Role</dt><dd>{ROLE_LABELS[a.role]}</dd>
              {a.phone && <><dt>Phone</dt><dd><a href={`tel:${a.phone}`}>{a.phone}</a></dd></>}
              {a.email && <><dt>Email</dt><dd>{a.email}</dd></>}
              {a.status !== "pending" && a.reviewed_at && (
                <><dt>{a.status === "active" ? "Approved" : "Rejected"}</dt><dd>{when(a.reviewed_at)}{a.reviewed_by ? ` by ${a.reviewed_by}` : ""}</dd></>
              )}
              {a.reason && <><dt>Reason</dt><dd>{a.reason}</dd></>}
            </dl>

            {a.status === "pending" && rejecting !== a.id && (
              <div className="actions">
                <button className="danger" disabled={busy === a.id}
                  onClick={() => { setRejecting(a.id); setReason(""); }}>Reject</button>
                <button disabled={busy === a.id} onClick={() => review(a, "approve")}>
                  {busy === a.id ? "Saving..." : "Approve"}
                </button>
              </div>
            )}

            {a.status === "pending" && rejecting === a.id && (
              <div className="stack" style={{ marginTop: 12 }}>
                <label>
                  Reason (optional)
                  <textarea value={reason} maxLength={255} onChange={(e) => setReason(e.target.value)}
                    placeholder="e.g. Not working at this station" />
                </label>
                <div className="actions">
                  <button className="secondary" onClick={() => setRejecting(null)}>Cancel</button>
                  <button className="danger" disabled={busy === a.id} onClick={() => review(a, "reject")}>
                    Confirm reject
                  </button>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </>
  );
}

// ---------------------------------------------------------------- the Requests tab
export default function Requests() {
  const [kind, setKind] = useState("drivers");
  const [counts, setCounts] = useState({ drivers: 0, staff: 0 });

  useEffect(() => {
    const load = () =>
      Promise.all([api.getDriverRequests("pending"), api.getStaffAccounts("pending")])
        .then(([d, s]) => setCounts({ drivers: d.length, staff: s.length }))
        .catch(() => {});
    load();
    window.addEventListener("driver-requests-changed", load);
    return () => window.removeEventListener("driver-requests-changed", load);
  }, []);

  const label = (text, n) => (n > 0 ? `${text} (${n})` : text);

  return (
    <>
      <div className="segments kinds" role="tablist" aria-label="Kind of request">
        <button role="tab" aria-selected={kind === "drivers"} className={kind === "drivers" ? "on" : ""}
          onClick={() => setKind("drivers")}>{label("Drivers", counts.drivers)}</button>
        <button role="tab" aria-selected={kind === "staff"} className={kind === "staff" ? "on" : ""}
          onClick={() => setKind("staff")}>{label("Staff accounts", counts.staff)}</button>
      </div>
      {kind === "drivers" ? <DriverRequests /> : <StaffAccounts />}
    </>
  );
}
