import { useEffect, useState } from "react";
import { api } from "../api.js";
import { useAsync } from "../hooks.js";
import { STATUSES, statusLabel } from "../components/Badges.jsx";
import { Empty, ErrorBox, Loading } from "../components/State.jsx";
import OpportunityTable from "../components/OpportunityTable.jsx";

export default function OpportunitiesPage() {
  const [verdict, setVerdict] = useState("");
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");

  // Wait for a pause in typing before querying.
  useEffect(() => {
    const timer = setTimeout(() => setQ(search.trim()), 300);
    return () => clearTimeout(timer);
  }, [search]);

  const { data, error, loading, reload } = useAsync(
    () => api.listOpportunities({ verdict, status, q }),
    [verdict, status, q],
  );

  return (
    <section>
      <h2>Opportunities</h2>
      <div className="filters">
        <label>
          Verdict
          <select value={verdict} onChange={(e) => setVerdict(e.target.value)}>
            <option value="">All</option>
            <option value="pass">Pass</option>
            <option value="maybe">Maybe</option>
            <option value="fail">Fail</option>
          </select>
        </label>
        <label>
          Status
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>{statusLabel(s)}</option>
            ))}
          </select>
        </label>
        <label className="grow">
          Search
          <input
            type="search"
            placeholder="Company, subject or sender"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
      </div>

      {loading && !data && <Loading what="opportunities" />}
      {error && <ErrorBox error={error} onRetry={reload} />}
      {data && data.length === 0 && (
        <Empty>No opportunities match. Submit a pitch to add one.</Empty>
      )}
      {data && data.length > 0 && <OpportunityTable rows={data} />}
    </section>
  );
}
