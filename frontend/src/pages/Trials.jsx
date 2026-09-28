import { useEffect, useMemo, useState } from "react";
import {
  getTrials, getLivePresets, importLiveTrials, apiErrorMessage,
} from "../services/api.js";
import { Banner, Loading, MetaChip } from "../components/ui.jsx";

/** One row in the trials table (expandable to show criteria). */
function TrialRow({ t }) {
  const [open, setOpen] = useState(false);
  const badge =
    t.status === "Recruiting" ? "eligible" : t.status === "Unknown" ? "insufficient" : "not-eligible";
  return (
    <>
      <tr className="clickable" onClick={() => setOpen((o) => !o)}>
        <td className="mono">{t.trial_id}</td>
        <td>{t.title}</td>
        <td><span className={`badge ${badge}`}>{t.status}</span></td>
        <td>{t.phase}</td>
        <td>{t.gender}</td>
        <td>{t.min_age ?? "any"}–{t.max_age ?? "any"}</td>
        <td className="hint">{(t.locations || []).slice(0, 2).join(" · ")}{(t.locations || []).length > 2 ? " …" : ""}</td>
        <td className="hint">{String(t.source || "").startsWith("ClinicalTrials.gov") ? "CTG live" : "CTRI demo"}</td>
      </tr>
      {open && (
        <tr>
          <td colSpan={8} style={{ background: "var(--soft, #f4fafb)" }}>
            <strong>{t.condition}</strong> · {t.study_type} · Sponsor: {t.sponsor || "Unknown"}
            <h3 style={{ margin: "0.5rem 0 0.2rem" }}>Inclusion criteria</h3>
            <ul className="hint" style={{ margin: 0 }}>{(t.inclusion_criteria || []).slice(0, 12).map((c, i) => <li key={i}>{c}</li>)}</ul>
            {(t.exclusion_criteria || []).length > 0 && (
              <>
                <h3 style={{ margin: "0.5rem 0 0.2rem" }}>Exclusion criteria</h3>
                <ul className="hint" style={{ margin: 0 }}>{t.exclusion_criteria.slice(0, 10).map((c, i) => <li key={i}>{c}</li>)}</ul>
              </>
            )}
          </td>
        </tr>
      )}
    </>
  );
}

export default function Trials() {
  const [trials, setTrials] = useState(null);
  const [filters, setFilters] = useState({ q: "", condition: "", status: "", phase: "", study_type: "" });
  const [presets, setPresets] = useState([]);
  const [imp, setImp] = useState({ condition: "", count: 8, indiaOnly: true, recruitingOnly: true });
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");

  const load = async () => {
    try {
      const res = await getTrials({
        q: filters.q || undefined,
        condition: filters.condition || undefined,
        status: filters.status || undefined,
        phase: filters.phase || undefined,
        study_type: filters.study_type || undefined,
      });
      setTrials(res);
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  };

  useEffect(() => { load(); /* eslint-disable-line react-hooks/exhaustive-deps */ }, [filters]);
  useEffect(() => {
    getLivePresets().then((r) => {
      setPresets(r.conditions || []);
      setImp((s) => ({ ...s, condition: r.conditions?.[0] || "" }));
    }).catch(() => setPresets([]));
  }, []);

  const facets = useMemo(() => {
    const list = trials?.trials || [];
    const uniq = (arr) => [...new Set(arr.filter(Boolean))].sort();
    return {
      conditions: uniq(list.map((t) => t.condition)),
      statuses: uniq(list.map((t) => t.status)),
      phases: uniq(list.map((t) => t.phase)),
      types: uniq(list.map((t) => t.study_type)),
    };
  }, [trials]);

  const doImport = async () => {
    if (!imp.condition) return;
    setBusy(`Fetching recruiting trials for “${imp.condition}” from ClinicalTrials.gov...`);
    setError(""); setMsg("");
    try {
      const res = await importLiveTrials(imp.condition, Number(imp.count), imp.indiaOnly, imp.recruitingOnly);
      setMsg(`Imported ${res.mapped} of ${res.fetched} fetched studies for “${res.condition_label}” `
             + `(${res.imported} written${res.skipped ? `, ${res.skipped} skipped` : ""}) · `
             + `database now holds ${res.total_in_database} trials.`);
      await load();
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setBusy("");
    }
  };

  return (
    <div>
      <h1>Trial Database</h1>
      <p style={{ color: "var(--muted)" }}>
        Every trial CTQ checks patients against — the bundled CTRI-format demo set plus real,
        currently-recruiting studies ingested live from ClinicalTrials.gov (India sites).
        Click a row to see its full criteria.
      </p>
      {error && <Banner kind="error">{error}</Banner>}
      {msg && <Banner kind="success">{msg}</Banner>}

      <div className="card section-gap">
        <h3>Live ingestion — import recruiting trials from ClinicalTrials.gov</h3>
        <p className="hint">
          Fetches real studies from the ClinicalTrials.gov API v2, maps them onto CTQ's trial schema
          (criteria, phase, age windows, India sites) and adds them to the database — they immediately
          flow through the same matching pipeline. Imports are kept across restarts.
        </p>
        <div className="btn-row" style={{ flexWrap: "wrap", alignItems: "center", gap: "0.6rem" }}>
          <select value={imp.condition} onChange={(e) => setImp({ ...imp, condition: e.target.value })}
            disabled={!!busy} style={{ minWidth: 220 }}>
            {presets.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
          <select value={imp.count} onChange={(e) => setImp({ ...imp, count: e.target.value })} disabled={!!busy}>
            {[5, 8, 10, 15, 20, 40].map((n) => <option key={n} value={n}>up to {n} studies</option>)}
          </select>
          <label className="check-item" style={{ fontSize: "0.85rem" }}>
            <input type="checkbox" checked={imp.indiaOnly}
              onChange={(e) => setImp({ ...imp, indiaOnly: e.target.checked })} /> India sites only
          </label>
          <label className="check-item" style={{ fontSize: "0.85rem" }}>
            <input type="checkbox" checked={imp.recruitingOnly}
              onChange={(e) => setImp({ ...imp, recruitingOnly: e.target.checked })} /> Recruiting only
          </label>
          <button type="button" className="btn primary" onClick={doImport} disabled={!!busy || !imp.condition}>
            ⤓ Import from ClinicalTrials.gov
          </button>
        </div>
        {busy && <Loading text={busy} />}
      </div>

      <div className="card section-gap">
        <div className="filters">
          <div className="field">
            <label>Search</label>
            <input placeholder="id, title, sponsor, location…"
              value={filters.q}
              onChange={(e) => setFilters({ ...filters, q: e.target.value })} />
          </div>
          <div className="field">
            <label>Condition</label>
            <select value={filters.condition}
              onChange={(e) => setFilters({ ...filters, condition: e.target.value })}>
              <option value="">All</option>{facets.conditions.map((c) => <option key={c}>{c}</option>)}
            </select>
          </div>
          <div className="field">
            <label>Status</label>
            <select value={filters.status}
              onChange={(e) => setFilters({ ...filters, status: e.target.value })}>
              <option value="">All</option>{facets.statuses.map((s) => <option key={s}>{s}</option>)}
            </select>
          </div>
          <div className="field">
            <label>Phase</label>
            <select value={filters.phase}
              onChange={(e) => setFilters({ ...filters, phase: e.target.value })}>
              <option value="">All</option>{facets.phases.map((p) => <option key={p}>{p}</option>)}
            </select>
          </div>
          <div className="field">
            <label>Type</label>
            <select value={filters.study_type}
              onChange={(e) => setFilters({ ...filters, study_type: e.target.value })}>
              <option value="">All</option>{facets.types.map((t) => <option key={t}>{t}</option>)}
            </select>
          </div>
        </div>
        {trials && (
          <p className="hint" style={{ margin: "0.5rem 0 0" }}>
            {trials.count} shown · {trials.total_in_database} in database
          </p>
        )}
        <div className="table-wrap section-gap">
          <table className="data">
            <thead>
              <tr>
                <th>Trial ID</th><th>Title</th><th>Status</th><th>Phase</th>
                <th>Gender</th><th>Age</th><th>Sites</th><th>Source</th>
              </tr>
            </thead>
            <tbody>
              {(trials?.trials || []).map((t) => <TrialRow key={t.trial_id} t={t} />)}
            </tbody>
          </table>
          {trials && trials.count === 0 && <Banner kind="warn">No trials match the current filters.</Banner>}
          {!trials && <Loading text="Loading trials…" />}
        </div>
        <div className="btn-row">
          <MetaChip>CTRI-format demo trials</MetaChip>
          <MetaChip>ClinicalTrials.gov live imports</MetaChip>
          <MetaChip>Same matching pipeline for both</MetaChip>
        </div>
      </div>
    </div>
  );
}
