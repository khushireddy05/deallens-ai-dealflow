import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { useAsync } from "../hooks.js";
import { VerdictBadge } from "../components/Badges.jsx";
import { ErrorBox } from "../components/State.jsx";

const EMPTY = { source: "email", sender: "", subject: "", body: "" };

export default function SubmitPage() {
  const [form, setForm] = useState(EMPTY);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const samples = useAsync(() => api.samples(), []);

  const set = (field) => (e) => setForm({ ...form, [field]: e.target.value });

  function loadSample(id) {
    const sample = samples.data?.find((s) => s.id === id);
    if (!sample) return;
    const { source, sender, subject, body } = sample.pitch;
    setForm({ source: source ?? "email", sender: sender ?? "", subject: subject ?? "", body });
    setResult(null);
    setError(null);
  }

  async function submit(e) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    setResult(null);
    try {
      setResult(await api.submitPitch(form));
    } catch (err) {
      setError(err);
    } finally {
      setSubmitting(false);
    }
  }

  const opportunity = result?.opportunity;

  return (
    <section>
      <h2>Submit a pitch</h2>
      <p className="muted">Paste an inbound email or form message. It is stored, enriched, extracted, screened and saved to the CRM.</p>

      <form onSubmit={submit}>
        <div className="row">
          <label>
            Load sample
            <select defaultValue="" onChange={(e) => loadSample(e.target.value)} disabled={!samples.data}>
              <option value="">{samples.error ? "Samples unavailable" : "Choose…"}</option>
              {samples.data?.map((s) => (
                <option key={s.id} value={s.id}>{s.label}</option>
              ))}
            </select>
          </label>
          <label>
            Source
            <select value={form.source} onChange={set("source")}>
              <option value="email">email</option>
              <option value="form">form</option>
              <option value="manual">manual</option>
            </select>
          </label>
        </div>
        <label>
          Sender
          <input value={form.sender} onChange={set("sender")} placeholder="founder@startup.com" />
        </label>
        <label>
          Subject
          <input value={form.subject} onChange={set("subject")} placeholder="Investment opportunity" />
        </label>
        <label>
          Message
          <textarea rows={10} value={form.body} onChange={set("body")} required />
        </label>
        <div>
          <button type="submit" className="primary" disabled={submitting || !form.body.trim()}>
            {submitting ? "Processing…" : "Process"}
          </button>
        </div>
      </form>

      {error && <ErrorBox error={error} />}

      {opportunity && (
        <div className="card result" role="status">
          {!result.created && (
            <p><strong>Already processed.</strong> This exact pitch was submitted before, so nothing new was created.</p>
          )}
          {result.created && opportunity.processing_state === "completed" && (
            <p><strong>Processed.</strong> Saved to the CRM as <em>{opportunity.company_name}</em>.</p>
          )}
          {result.created && opportunity.processing_state === "failed" && (
            <p>
              <strong>Could not be processed</strong> at the “{opportunity.failed_step}” step: {opportunity.error}
              {" "}The pitch was kept — see <Link to="/failures">Failures</Link>.
            </p>
          )}
          <p>
            <VerdictBadge verdict={opportunity.verdict} state={opportunity.processing_state} />{" "}
            <Link to={`/opportunities/${opportunity.id}`}>Open opportunity #{opportunity.id}</Link>
          </p>
        </div>
      )}
    </section>
  );
}
