import { useState } from "react";
import { Banner, EligibilityBadge } from "./ui.jsx";
import { exportResultsExcel, apiErrorMessage } from "../services/api.js";

function verdictColor(e) {
  return e === "Potentially Eligible" ? "#1a7f37"
    : e === "Not Eligible" ? "#b02a37"
    : "#8a6d00";
}

const TH = { textAlign: "left", padding: "0.45rem 0.55rem", whiteSpace: "nowrap",
             borderBottom: "2px solid rgba(128,128,128,.35)", position: "sticky", top: 0,
             background: "inherit", backdropFilter: "blur(4px)" };
const TD = { padding: "0.4rem 0.55rem", verticalAlign: "middle" };

/**
 * Tabular patient x trial view of a cohort run (structured or unstructured),
 * with a "download as Excel" button backed by /cohort/export-results.
 *
 * patients: the payloads that were submitted (for the summary sheet)
 * results:  cohort rows [{patient_id, ok, response | error}]
 */
export default function ResultsTable({ patients = [], results = [] }) {
  const [onlyEligible, setOnlyEligible] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [dlErr, setDlErr] = useState("");

  const ok = results.filter((r) => r.ok);
  const failed = results.filter((r) => !r.ok);

  const allRows = [];
  for (const r of ok) {
    for (const t of r.response?.results || []) {
      allRows.push({ pid: r.patient_id, t });
    }
  }
  const rows = onlyEligible
    ? allRows.filter((x) => x.t.eligibility === "Potentially Eligible")
    : allRows;

  const download = async () => {
    setDownloading(true);
    setDlErr("");
    try {
      const blob = await exportResultsExcel(patients, results);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `ctq_matching_results_${new Date().toISOString().slice(0, 10)}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setDlErr(apiErrorMessage(err));
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="section-gap">
      <div className="btn-row" style={{ flexWrap: "wrap", alignItems: "center", gap: "0.6rem" }}>
        <strong>Results table</strong>
        <label style={{ display: "flex", alignItems: "center", gap: "0.3rem", fontSize: "0.85rem", cursor: "pointer" }}>
          <input type="checkbox" checked={onlyEligible}
            onChange={(e) => setOnlyEligible(e.target.checked)} />
          Only Potentially Eligible
        </label>
        <button type="button" className="btn" onClick={download}
          disabled={downloading || allRows.length === 0}>
          {downloading ? "Preparing Excel..." : "⤓ Download results (Excel)"}
        </button>
        <span className="hint">
          {rows.length} of {allRows.length} patient-trial rows
          {failed.length > 0 && <> · {failed.length} patient(s) failed</>}
        </span>
      </div>
      {dlErr && <Banner kind="error">{dlErr}</Banner>}
      <div style={{ maxHeight: 460, overflow: "auto",
                    border: "1px solid rgba(128,128,128,.3)", borderRadius: 8, marginTop: "0.5rem" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.82rem" }}>
          <thead>
            <tr>
              {["Patient", "Trial", "Title", "Eligibility", "Match", "Phase", "Key reasons"].map((h) => (
                <th key={h} style={TH}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map(({ pid, t }) => (
              <tr key={`${pid}-${t.trial_id}`} style={{ borderBottom: "1px solid rgba(128,128,128,.18)" }}>
                <td style={{ ...TD, fontWeight: 600, whiteSpace: "nowrap" }}>{pid}</td>
                <td style={TD}>{t.trial_id}</td>
                <td style={{ ...TD, maxWidth: 320 }}>
                  <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
                       title={t.title}>{t.title}</div>
                </td>
                <td style={TD}><EligibilityBadge status={t.eligibility} /></td>
                <td style={{ ...TD, fontWeight: 600, color: verdictColor(t.eligibility), whiteSpace: "nowrap" }}>
                  {t.match_percent ?? Math.round((t.similarity_score || 0) * 100)}%
                </td>
                <td style={TD}>{t.phase}</td>
                <td style={{ ...TD, maxWidth: 300, color: "rgba(128,128,128,1)" }}>
                  <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
                       title={[...(t.reasons_for || []), ...(t.reasons_against || []),
                               ...(t.failed_criteria || [])].join("  |  ")}>
                    {(t.reasons_for || []).slice(0, 2).join("; ")
                      || (t.reasons_against || [])[0]
                      || (t.missing_information || [])[0]
                      || "—"}
                  </div>
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={7} style={{ padding: "0.9rem", textAlign: "center", color: "rgba(128,128,128,1)" }}>
                  {onlyEligible
                    ? "No Potentially Eligible rows — untick the filter to see every check."
                    : "No result rows."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
