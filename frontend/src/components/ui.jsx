const STATUS_CLASS = {
  "Potentially Eligible": "eligible",
  "Not Eligible": "not-eligible",
  "Insufficient Information": "insufficient",
};

const STATUS_ICON = {
  "Potentially Eligible": "\u2713",
  "Not Eligible": "\u2717",
  "Insufficient Information": "?",
};

/** Coloured eligibility badge. */
export function EligibilityBadge({ status }) {
  return (
    <span className={`badge ${STATUS_CLASS[status] || "neutral"}`}>
      {STATUS_ICON[status] || ""} {status}
    </span>
  );
}

/** Displayed match score - semantic similarity, never an eligibility probability. */
export function MatchScore({ percent, similarity }) {
  const tip = similarity != null
    ? `Cosine similarity ${Number(similarity).toFixed(3)} between the patient profile and the trial text (semantic similarity, not a probability of eligibility).`
    : "";
  return (
    <span className="score-pill" title={tip} style={{ cursor: "help" }}>
      Match Score: {percent}%
    </span>
  );
}

/** One explanation line with a coloured marker. */
export function Reason({ kind, children }) {
  const icon = kind === "for" ? "\u2713" : kind === "against" ? "\u2717" : "?";
  return (
    <div className={`reason ${kind}`}>
      <span className="icon">{icon}</span>
      <span>{children}</span>
    </div>
  );
}

export function Loading({ text = "Working..." }) {
  return (
    <div className="loading">
      <div className="spinner" />
      <p>{text}</p>
    </div>
  );
}

export function Banner({ kind = "info", children }) {
  return <div className={`banner ${kind}`}>{children}</div>;
}

/** Small pill for trial metadata chips. */
export function MetaChip({ children }) {
  return <span className="meta-chip">{children}</span>;
}
