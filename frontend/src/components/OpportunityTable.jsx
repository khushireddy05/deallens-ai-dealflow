import { Link } from "react-router-dom";
import { StatusBadge, VerdictBadge } from "./Badges.jsx";

export function formatDate(value) {
  if (!value) return "";
  return new Date(value).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export default function OpportunityTable({ rows, showError = false, renderAction }) {
  return (
    <table>
      <thead>
        <tr>
          <th>Company</th>
          <th>Location</th>
          <th>Stage</th>
          <th>Verdict</th>
          <th>Status</th>
          <th>{showError ? "Error" : "Received"}</th>
          {renderAction && <th></th>}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.id}>
            <td>
              <Link to={`/opportunities/${row.id}`}>
                {row.company_name ?? row.subject ?? `Opportunity #${row.id}`}
              </Link>
              {row.company_domain && <div className="muted small">{row.company_domain}</div>}
            </td>
            <td>{row.location ?? "—"}</td>
            <td>{row.funding_stage ?? "—"}</td>
            <td><VerdictBadge verdict={row.verdict} state={row.processing_state} /></td>
            <td><StatusBadge status={row.status} /></td>
            <td>
              {showError ? (
                <span className="small">
                  <strong>{row.failed_step}:</strong> {row.error}
                </span>
              ) : (
                formatDate(row.received_at)
              )}
            </td>
            {renderAction && <td>{renderAction(row)}</td>}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
