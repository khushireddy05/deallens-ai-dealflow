import { useEffect, useState } from "react";
import { api } from "../api.js";
import { useAsync } from "../hooks.js";
import { Empty, ErrorBox, Loading } from "../components/State.jsx";

export default function CompaniesPage() {
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");

  useEffect(() => {
    const timer = setTimeout(() => setQ(search.trim()), 300);
    return () => clearTimeout(timer);
  }, [search]);

  const { data, error, loading, reload } = useAsync(() => api.listCompanies({ q }), [q]);

  return (
    <section>
      <h2>Companies</h2>
      <p className="muted">
        One row per company. Repeat pitches from the same company are merged, not duplicated.
      </p>
      <div className="filters">
        <label className="grow">
          Search
          <input
            type="search"
            placeholder="Name or domain"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
      </div>

      {loading && !data && <Loading what="companies" />}
      {error && <ErrorBox error={error} onRetry={reload} />}
      {data && data.length === 0 && <Empty>No companies yet.</Empty>}
      {data && data.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Company</th>
              <th>Location</th>
              <th>Industry</th>
              <th>Stage</th>
              <th>Pitches</th>
            </tr>
          </thead>
          <tbody>
            {data.map((company) => (
              <tr key={company.id}>
                <td>
                  {company.name}
                  {company.needs_review && (
                    <span
                      className="badge badge-warn"
                      title="No website was given, so this record was matched by name only. Check it is not a duplicate."
                    >
                      Needs review
                    </span>
                  )}
                  <div className="muted small">{company.domain ?? "no domain"}</div>
                </td>
                <td>{company.location ?? "—"}</td>
                <td>{company.industry ?? "—"}</td>
                <td>{company.funding_stage ?? "—"}</td>
                <td>{company.opportunity_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
