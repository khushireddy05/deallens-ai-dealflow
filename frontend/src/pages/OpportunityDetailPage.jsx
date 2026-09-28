import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api.js";
import { useAsync } from "../hooks.js";
import { STATUSES, StatusBadge, VerdictBadge, statusLabel } from "../components/Badges.jsx";
import { ErrorBox, Loading } from "../components/State.jsx";

const FIELDS = [
  ["Company", "company_name"],
  ["Domain", "domain"],
  ["Location", "location"],
  ["Country", "country"],
  ["Industry", "industry"],
  ["Product", "product"],
  ["Funding stage", "funding_stage"],
  ["Funding amount", "funding_amount"],
  ["Founders", "founders"],
  ["Description", "description"],
];

function fmt(value) {
  if (value === null || value === undefined || value === "") return "—";
  return Array.isArray(value) ? (value.length ? value.join(", ") : "—") : String(value);
}

export default function OpportunityDetailPage() {
  const { id } = useParams();
  const { data, error, loading, reload } = useAsync(() => api.getOpportunity(id), [id]);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState(null);

  async function act(fn) {
    setBusy(true);
    setActionError(null);
    try {
      await fn();
      reload();
    } catch (err) {
      setActionError(err);
    } finally {
      setBusy(false);
    }
  }

  if (loading && !data) return <Loading what="opportunity" />;
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  if (!data) return null;

  const failed = data.processing_state === "failed";
  const extracted = data.extracted ?? {};

  return (
    <section>
      <p><Link to="/">← Opportunities</Link></p>
      <h2>
        {data.company_name ?? data.subject ?? `Opportunity #${data.id}`}{" "}
        <VerdictBadge verdict={data.verdict} state={data.processing_state} />
      </h2>
      <p className="muted">
        {data.company_domain ?? "no domain"} · via {data.source}
        {data.sender ? ` from ${data.sender}` : ""} · <StatusBadge status={data.status} />
        {data.company?.needs_review && <span className="badge badge-warn">Company needs review</span>}
      </p>

      <div className="card">
        <h3>Human review</h3>
        <div className="status-buttons" role="group" aria-label="Review status">
          {STATUSES.map((status) => (
            <button
              key={status}
              className={data.status === status ? "active" : ""}
              aria-pressed={data.status === status}
              disabled={busy}
              onClick={() => act(() => api.setStatus(data.id, status))}
            >
              {statusLabel(status)}
            </button>
          ))}
        </div>
        <p className="muted small">Your decision is stored separately from the automated verdict.</p>
        {actionError && <ErrorBox error={actionError} />}
      </div>

      {failed && (
        <div className="card card-error">
          <h3>Processing failed</h3>
          <p><strong>{data.failed_step}:</strong> {data.error}</p>
          <button disabled={busy} onClick={() => act(() => api.retry(data.id))}>Retry</button>
        </div>
      )}

      {data.verdict && (
        <div className="card">
          <h3>Screening</h3>
          <ul className="reasons">
            {data.screening_reasons.map((reason) => <li key={reason}>{reason}</li>)}
          </ul>
        </div>
      )}

      {Object.keys(extracted).length > 0 && (
        <div className="card">
          <h3>Extracted by the model</h3>
          <dl>
            {FIELDS.map(([label, key]) => (
              <div key={key} className="dl-row">
                <dt>{label}</dt>
                <dd>{fmt(extracted[key])}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}

      <div className="card">
        <h3>Timeline</h3>
        <ol className="timeline">
          {data.logs.map((log) => (
            <li key={log.id} className={`log-${log.status}`}>
              <span className="log-step">{log.step}</span>
              <span className={`badge badge-log-${log.status}`}>{log.status}</span>
              {log.message && <span className="muted small"> {log.message}</span>}
              <span className="muted small log-time">{new Date(log.created_at).toLocaleTimeString()}</span>
            </li>
          ))}
        </ol>
      </div>

      {data.enrichment && (
        <details className="card">
          <summary>Website information used for context</summary>
          <p className="small"><a href={data.enrichment.url} target="_blank" rel="noreferrer noopener">{data.enrichment.url}</a></p>
          <p><strong>{data.enrichment.title}</strong></p>
          <p>{data.enrichment.description}</p>
          <p className="muted small">{data.enrichment.text_excerpt}</p>
        </details>
      )}

      <div className="card">
        <h3>Original pitch</h3>
        {data.subject && <p><strong>{data.subject}</strong></p>}
        <pre>{data.raw_body}</pre>
      </div>
    </section>
  );
}
