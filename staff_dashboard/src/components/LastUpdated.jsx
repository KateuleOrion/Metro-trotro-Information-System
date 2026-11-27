export default function LastUpdated({ value }) {
  return (
    <p className="updated">
      Last updated: {value ? new Date(value).toLocaleString() : "No updates yet"}
    </p>
  );
}
