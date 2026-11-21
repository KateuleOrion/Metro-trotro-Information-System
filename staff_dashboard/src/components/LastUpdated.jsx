export default function LastUpdated({ value }) {
  return (
    <p className="muted">
      Last updated: {value ? new Date(value).toLocaleString() : "No updates yet"}
    </p>
  );
}
