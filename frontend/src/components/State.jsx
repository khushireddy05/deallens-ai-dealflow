export function Loading({ what = "data" }) {
  return <p className="state" role="status">Loading {what}…</p>;
}

export function ErrorBox({ error, onRetry }) {
  return (
    <div className="state state-error" role="alert">
      <p>{error?.message ?? "Something went wrong."}</p>
      {onRetry && <button onClick={onRetry}>Try again</button>}
    </div>
  );
}

export function Empty({ children }) {
  return <p className="state state-empty">{children}</p>;
}
