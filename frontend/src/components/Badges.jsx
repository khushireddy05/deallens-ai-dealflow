const VERDICT_LABELS = { pass: "Pass", maybe: "Maybe", fail: "Fail" };
const STATUS_LABELS = {
  new: "New",
  in_review: "In review",
  passed: "Passed",
  rejected: "Rejected",
};

export const STATUSES = Object.keys(STATUS_LABELS);
export const statusLabel = (status) => STATUS_LABELS[status] ?? status;

export function VerdictBadge({ verdict, state }) {
  if (state === "failed") return <span className="badge badge-failed">Failed</span>;
  if (!verdict) return <span className="badge badge-muted">Pending</span>;
  return <span className={`badge badge-${verdict}`}>{VERDICT_LABELS[verdict]}</span>;
}

export function StatusBadge({ status }) {
  return <span className={`badge badge-status-${status}`}>{statusLabel(status)}</span>;
}
