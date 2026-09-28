import { useState } from "react";
import { api } from "../api.js";
import { useAsync } from "../hooks.js";
import { Empty, ErrorBox, Loading } from "../components/State.jsx";
import OpportunityTable from "../components/OpportunityTable.jsx";

export default function FailuresPage() {
  const { data, error, loading, reload } = useAsync(() => api.listFailures(), []);
  const [retrying, setRetrying] = useState(null);
  const [retryError, setRetryError] = useState(null);

  async function retry(id) {
    setRetrying(id);
    setRetryError(null);
    try {
      await api.retry(id);
    } catch (err) {
      setRetryError(err);
    } finally {
      setRetrying(null);
      reload();
    }
  }

  return (
    <section>
      <h2>Failures</h2>
      <p className="muted">
        Pitches that could not be processed. The original text is kept; nothing invalid was
        written to the CRM. Fix the cause (for example the API key) and retry.
      </p>

      {loading && !data && <Loading what="failures" />}
      {error && <ErrorBox error={error} onRetry={reload} />}
      {retryError && <ErrorBox error={retryError} />}
      {data && data.length === 0 && <Empty>No failed items.</Empty>}
      {data && data.length > 0 && (
        <OpportunityTable
          rows={data}
          showError
          renderAction={(row) => (
            <button
              aria-label={`Retry #${row.id}`}
              disabled={retrying === row.id}
              onClick={() => retry(row.id)}
            >
              {retrying === row.id ? "Retrying…" : "Retry"}
            </button>
          )}
        />
      )}
    </section>
  );
}
