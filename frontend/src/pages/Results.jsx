import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { getTrial, apiErrorMessage } from "../services/api.js";
import { EligibilityBadge, MatchScore, Reason, Banner, MetaChip } from "../components/ui.jsx";
import ResultsTable from "../components/ResultsTable.jsx";

const STATUSES = ["Potentially Eligible", "Partially Eligible", "Not Eligible"];

/** Full trial details, fetched on demand from the trial database. */
function TrialDetailModal({ trialId, onClose }) {
  const [trial, setTrial] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    setTrial(null);
    setError("");
    if (trialId) {
      getTrial(trialId).then(setTrial).catch((e) => setError(apiErrorMessage(e)));
    }
  }, [trialId]);

  if (!trialId) return null;
  return (
    <div style={{
      position: "fixed", inset: 0, background: "rgba(15, 40, 50, 0.55)", zIndex: 100,
      display: "flex", alignItems: "flex-start", justifyContent: "center", padding: "2.5rem 1rem", overflowY: "auto",
    }} onClick={onClose}>
      <div className="card" style={{ maxWidth: 760, width: "100%" }} onClick={(e) => e.stopPropagation()}>
        {error && <Banner kind="error">{error}</Banner>}
        {!trial && !error && <div className="loading"><div className="spinner" /><p>Loading trial...</p></div>}
        {trial && (
          <>
            <div className="result-head">
              <div>
                <div className="trial-id">{trial.trial_id}</div>
                <h2>{trial.title}</h2>
              </div>
              <button className="btn secondary" onClick={onClose}>Close</button>
            </div>
            <div className="result-meta">
              <span className="badge neutral">{trial.status}</span>
              <MetaChip>Phase: {trial.phase}</MetaChip>
              <MetaChip>Type: {trial.study_type}</MetaChip>
              <MetaChip>Gender: {trial.gender}</MetaChip>
              <MetaChip>Age: {trial.min_age ?? "any"} - {trial.max_age ?? "any"} years</MetaChip>
            </div>
            <h3 className="section-gap">Condition &amp; Intervention</h3>
            <p>{trial.condition}</p>
            <p>{(trial.interventions || []).join(", ") || "Observational - no intervention"}</p>
            <h3>Inclusion Criteria</h3>
            <ul>{(trial.inclusion_criteria || []).map((c, i) => <li key={i}>{c}</li>)}</ul>
            <h3>Exclusion Criteria</h3>
            <ul>{(trial.exclusion_criteria || []).map((c, i) => <li key={i}>{c}</li>)}</ul>
            <h3>Locations</h3>
            <p>{(trial.locations || []).join(" · ") || "Not listed"}</p>
            <div className="kv section-gap">
              <div>Sponsor</div><div>{trial.sponsor || "Not listed"}</div>
              <div>Source</div><div>{trial.source}</div>
              <div>Last updated</div><div>{trial.last_updated || "Unknown"}</div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default function Results() {
  const [query, setQuery] = useState(() => {
    try { return JSON.parse(sessionStorage.getItem("ctq_results")); } catch { return null; }
  });
  const [detail, setDetail] = useState(null);
  const [filters, setFilters] = useState({ eligibility: "All", disease: "All", state: "All", status: "All", phase: "All", sort: "match" });

  const results = query?.response?.results || [];
  const warnings = query?.response?.warnings || [];

  const downloadCsv = () => {
    const esc = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
    const header = "trial_id,title,condition,eligibility,match_percent,similarity,status,phase,locations,reasons_for,reasons_against,missing_information";
    const lines = shown.map((r) => [
      r.trial_id, r.title, r.condition, r.eligibility,
      r.match_percent ?? Math.round((r.similarity_score || 0) * 100),
      r.similarity_score ?? "", r.status, r.phase,
      (r.locations || []).join(" | "),
      (r.reasons_for || []).join(" | "),
      (r.reasons_against || []).join(" | "),
      (r.missing_information || []).join(" | "),
    ].map(esc).join(","));
    const blob = new Blob([header + "\n" + lines.join("\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `ctq_trial_results_${new Date().toISOString().slice(0, 10)}.csv`; a.click();
    URL.revokeObjectURL(url);
  };

  const facets = useMemo(() => {
    const uniq = (arr) => [...new Set(arr.filter(Boolean))].sort();
    return {
      diseases: uniq(results.map((r) => r.condition)),
      states: uniq(results.flatMap((r) => (r.locations || []).map((l) => l.split(",").pop().trim()))),
      statuses: uniq(results.map((r) => r.status)),
      phases: uniq(results.map((r) => r.phase)),
    };
  }, [results]);

  const shown = useMemo(() => {
    let list = [...results];
    if (filters.eligibility !== "All") list = list.filter((r) => r.eligibility === filters.eligibility);
    if (filters.disease !== "All") list = list.filter((r) => r.condition === filters.disease);
    if (filters.state !== "All") list = list.filter((r) => (r.locations || []).some((l) => l.includes(filters.state)));
    if (filters.status !== "All") list = list.filter((r) => r.status === filters.status);
    if (filters.phase !== "All") list = list.filter((r) => r.phase === filters.phase);
    if (filters.sort === "match") list.sort((a, b) => b.similarity_score - a.similarity_score);
    if (filters.sort === "eligible") list.sort((a, b) =>
      (["Potentially Eligible", "Partially Eligible", "Not Eligible"].indexOf(a.eligibility)
        - ["Potentially Eligible", "Partially Eligible", "Not Eligible"].indexOf(b.eligibility))
      || ((b.similarity_score || 0) - (a.similarity_score || 0)));
    return list;
  }, [results, filters]);

  if (!query) {
    return (
      <div>
        <h1>Trial Results</h1>
        <Banner kind="warn">
          No analysis found in this session. Please <Link to="/matcher">enter patient details</Link> first.
        </Banner>
      </div>
    );
  }

  const counts = STATUSES.map((s) => results.filter((r) => r.eligibility === s).length);

  return (
    <div>
      <div className="result-head" style={{ alignItems: "baseline", marginBottom: "0.5rem" }}>
        <h1>Your Trial Matches</h1>
        <Link to="/matcher" className="btn secondary" style={{ padding: "0.45rem 1rem" }}>New search</Link>
      </div>
      <p style={{ color: "var(--muted)", fontSize: "0.95rem", marginBottom: "1rem" }}>
        {results.length} trials · {counts[0]} potentially eligible · {counts[1]} not eligible · {counts[2]} need more info
      </p>

      {warnings.length > 0 && (
        <Banner kind="warn">
          <strong>Input notes:</strong>
          <ul style={{ margin: "0.3rem 0 0" }}>{warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>
        </Banner>
      )}

      {/* -------- Filters -------- */}
      <div className="card section-gap">
        <div className="filters">
          <div className="field">
            <label>Eligibility</label>
            <select value={filters.eligibility} onChange={(e) => setFilters({ ...filters, eligibility: e.target.value })}>
              <option>All</option>{STATUSES.map((s) => <option key={s}>{s}</option>)}
            </select>
          </div>
          <div className="field">
            <label>Match score</label>
            <select value={filters.sort} onChange={(e) => setFilters({ ...filters, sort: e.target.value })}>
              <option value="match">Highest match score first</option>
              <option value="eligible">Eligible first</option>
            </select>
          </div>
          <div className="field">
            <label>Disease</label>
            <select value={filters.disease} onChange={(e) => setFilters({ ...filters, disease: e.target.value })}>
              <option>All</option>{facets.diseases.map((d) => <option key={d}>{d}</option>)}
            </select>
          </div>
          <div className="field">
            <label>State</label>
            <select value={filters.state} onChange={(e) => setFilters({ ...filters, state: e.target.value })}>
              <option>All</option>{facets.states.map((s) => <option key={s}>{s}</option>)}
            </select>
          </div>
          <div className="field">
            <label>Recruitment status</label>
            <select value={filters.status} onChange={(e) => setFilters({ ...filters, status: e.target.value })}>
              <option>All</option>{facets.statuses.map((s) => <option key={s}>{s}</option>)}
            </select>
          </div>
          <div className="field">
            <label>Phase</label>
            <select value={filters.phase} onChange={(e) => setFilters({ ...filters, phase: e.target.value })}>
              <option>All</option>{facets.phases.map((p) => <option key={p}>{p}</option>)}
            </select>
          </div>
        </div>
      </div>

      {/* -------- Result cards -------- */}
      {shown.length === 0 && <Banner kind="warn">No trials match the current filters.</Banner>}
      {shown.map((r) => (
        <div key={r.trial_id} className={`card result-card section-gap ${r.eligibility === "Potentially Eligible" ? "eligible" : r.eligibility === "Not Eligible" ? "not-eligible" : "insufficient"}`}>
          <div className="result-head">
            <div>
              <div className="trial-id">{r.trial_id}</div>
              <div className="result-title">{r.title}</div>
              <div className="result-meta">
                <EligibilityBadge status={r.eligibility} />
                <MatchScore percent={r.match_percent ?? Math.round(r.similarity_score * 100)} similarity={r.similarity_score} />
                <MetaChip>{r.condition}</MetaChip>
                <MetaChip>{r.status}</MetaChip>
                <MetaChip>{r.phase}</MetaChip>
                <MetaChip>{(r.locations || []).slice(0, 2).join(" · ")}{(r.locations || []).length > 2 ? " …" : ""}</MetaChip>
              </div>
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "0 2rem" }}>
            <div>
              <h3>Why?</h3>
              {r.reasons_for.length === 0 && <p className="hint">No satisfied criteria identified.</p>}
              {r.reasons_for.map((x, i) => <Reason key={`f${i}`} kind="for">{x}</Reason>)}
              {r.reasons_against.length === 0 && r.eligibility === "Potentially Eligible" && (
                <p className="hint">No known exclusion criterion detected.</p>
              )}
              {r.reasons_against.map((x, i) => <Reason key={`a${i}`} kind="against">{x}</Reason>)}
            </div>
            {r.missing_information.length > 0 && (
              <div>
                <h3>Missing information</h3>
                {r.missing_information.map((x, i) => <Reason key={`m${i}`} kind="missing">{x}</Reason>)}
                {r.eligibility === "Partially Eligible" && (
                  <p className="hint">Classified as <strong>Partially Eligible</strong> - supply the missing details above for a firmer verdict.</p>
                )}
              </div>
            )}
          </div>

          <div className="btn-row section-gap">
            <button className="btn secondary" onClick={() => setDetail(r.trial_id)}>View Full Trial</button>
          </div>
        </div>
      ))}

      {results.length > 0 && (
        <ResultsTable
          patients={[query.profile || {}]}
          results={[{ patient_id: query.response?.patient_id || "P001", ok: true, response: query.response }]}
        />
      )}

      {results.length > 0 && (
        <div className="btn-row section-gap" style={{ justifyContent: "center" }}>
          <button className="btn primary" onClick={downloadCsv}>
            ⤓ Download results (CSV)
          </button>
          <span className="hint">Exports all {results.length} trial verdicts above to a spreadsheet.</span>
        </div>
      )}

      <TrialDetailModal trialId={detail} onClose={() => setDetail(null)} />
    </div>
  );
}
