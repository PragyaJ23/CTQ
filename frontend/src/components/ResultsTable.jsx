import { useState } from "react";
import { Banner, EligibilityBadge } from "./ui.jsx";
import { exportResultsExcel, apiErrorMessage } from "../services/api.js";

function verdictColor(e) {
  return e === "Potentially Eligible" ? "#1a7f37"
    : e === "Not Eligible" ? "#b02a37"
    : "#8a6d00"; // Partially Eligible (and any legacy verdict)
}

/** Verdict label in the chosen language; reasons always stay English. */
const HI_VERDICT = {
  "Potentially Eligible": "पात्र",
  "Partially Eligible": "आंशिक रूप से पात्र",
  "Not Eligible": "पात्र नहीं",
};
const HI_HEADER = {
  Patient: "मरीज़", Trial: "ट्रायल", Title: "शीर्षक", Eligibility: "पात्रता",
  Match: "मैच %", Phase: "चरण", "Key reasons": "मुख्य कारण",
};

const TH = { textAlign: "left", padding: "0.45rem 0.55rem", whiteSpace: "nowrap",
             borderBottom: "2px solid rgba(128,128,128,.35)", position: "sticky", top: 0,
             background: "inherit", backdropFilter: "blur(4px)" };
const TD = { padding: "0.4rem 0.55rem", verticalAlign: "middle" };

/**
 * Per-patient tabular results for a cohort run (structured or unstructured):
 * a button per patient ("Patient 1", "Patient 2", ... plus "All patients")
 * shows one table at a time, with an English/हिंदी toggle and an Excel
 * download (Hindi mode adds Hindi sheets) backed by /cohort/export-results.
 *
 * patients: the payloads that were submitted (for the Excel summary sheet)
 * results:  cohort rows [{patient_id, ok, response | error}]
 * onOpen:   optional (patient_id) => void - renders an Open button per row
 */
export default function ResultsTable({ patients = [], results = [], onOpen }) {
  const [activeP, setActiveP] = useState(0); // index into ok patients; ok.length = "All"
  const [onlyEligible, setOnlyEligible] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [dlErr, setDlErr] = useState("");
  const [lang, setLang] = useState("en");
  const hi = lang === "hi";
  const label = (en) => (hi ? HI_HEADER[en] || en : en);

  const ok = results.filter((r) => r.ok);
  const failed = results.filter((r) => !r.ok);

  const allRows = [];
  ok.forEach((r, pidx) => {
    for (const t of r.response?.results || []) {
      allRows.push({ pid: r.patient_id, pidx, t });
    }
  });

  const showAll = activeP >= ok.length;
  const scopedRows = showAll ? allRows : allRows.filter((x) => x.pidx === activeP);
  const rows = onlyEligible
    ? scopedRows.filter((x) => x.t.eligibility === "Potentially Eligible")
    : scopedRows;

  // per-patient verdict counts for the button badges + summary line
  const countsByPatient = ok.map((r) => {
    const c = { total: 0, pe: 0, partial: 0, ne: 0 };
    for (const t of r.response?.results || []) {
      c.total += 1;
      if (t.eligibility === "Potentially Eligible") c.pe += 1;
      else if (t.eligibility === "Partially Eligible") c.partial += 1;
      else c.ne += 1;
    }
    return c;
  });
  const activeCounts = showAll
    ? countsByPatient.reduce((a, c) => ({ total: a.total + c.total, pe: a.pe + c.pe,
                                          partial: a.partial + c.partial, ne: a.ne + c.ne }),
                             { total: 0, pe: 0, partial: 0, ne: 0 })
    : countsByPatient[activeP] || { total: 0, pe: 0, partial: 0, ne: 0 };

  const download = async () => {
    setDownloading(true);
    setDlErr("");
    try {
      const blob = await exportResultsExcel(patients, results, hi ? "hi" : "en");
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

  const columns = showAll
    ? ["Patient", "Trial", "Title", "Eligibility", "Match", "Phase", "Key reasons"]
    : ["Trial", "Title", "Eligibility", "Match", "Phase", "Key reasons"];

  return (
    <div className="section-gap">
      <div className="btn-row" style={{ flexWrap: "wrap", alignItems: "center", gap: "0.6rem" }}>
        <strong>{hi ? "परिणाम तालिका" : "Results table"}</strong>
        <label style={{ display: "flex", alignItems: "center", gap: "0.3rem", fontSize: "0.85rem", cursor: "pointer" }}>
          <input type="checkbox" checked={onlyEligible}
            onChange={(e) => setOnlyEligible(e.target.checked)} />
          {hi ? "केवल पूर्ण पात्र" : "Only Potentially Eligible"}
        </label>
        <div style={{ display: "flex", gap: 0 }}>
          {["en", "hi"].map((l) => (
            <button key={l} type="button" className={`btn ${lang === l ? "primary" : "secondary"}`}
              style={{ padding: "0.25rem 0.7rem", fontSize: "0.8rem" }}
              onClick={() => setLang(l)}>
              {l === "en" ? "English" : "हिंदी"}
            </button>
          ))}
        </div>
        <button type="button" className="btn" onClick={download}
          disabled={downloading || allRows.length === 0}>
          {downloading ? (hi ? "Excel तैयार हो रहा है..." : "Preparing Excel...")
            : hi ? "⤓ परिणाम डाउनलोड करें (Excel)" : "⤓ Download results (Excel)"}
        </button>
        <span className="hint">
          {hi ? `${rows.length} / ${scopedRows.length} पंक्तियाँ`
            : <>{rows.length} of {scopedRows.length} rows</>}
          {failed.length > 0 && <> · {hi ? `${failed.length} मरीज़ असफल` : `${failed.length} patient(s) failed`}</>}
        </span>
      </div>

      {/* ---- per-patient buttons ---- */}
      <div className="btn-row" style={{ flexWrap: "wrap", gap: "0.35rem", margin: "0.5rem 0 0.2rem" }}>
        {ok.map((r, i) => (
          <button key={r.patient_id} type="button"
            className={`btn ${i === activeP ? "primary" : "secondary"}`}
            style={{ padding: "0.3rem 0.75rem", fontSize: "0.8rem" }}
            onClick={() => setActiveP(i)}>
            {hi ? `मरीज़ ${i + 1}` : `Patient ${i + 1}`}
            {" · "}
            <span style={{ color: verdictColor("Potentially Eligible") }}>{countsByPatient[i].pe}</span>
          </button>
        ))}
        <button type="button" className={`btn ${showAll ? "primary" : "secondary"}`}
          style={{ padding: "0.3rem 0.75rem", fontSize: "0.8rem" }}
          onClick={() => setActiveP(ok.length)}>
          {hi ? "सभी मरीज़" : "All patients"}
        </button>
      </div>

      {/* ---- summary line for the active view ---- */}
      <p className="hint" style={{ margin: "0.2rem 0 0.4rem" }}>
        {showAll
          ? (hi ? `सभी ${ok.length} मरीज़ मिलकर` : `All ${ok.length} patients combined`)
          : (hi ? `${ok[activeP]?.patient_id || `मरीज़ ${activeP + 1}`}` : ok[activeP]?.patient_id || `Patient ${activeP + 1}`)}
        {" · "}
        {hi
          ? `${activeCounts.total} ट्रायल जाँचे · ${activeCounts.pe} पात्र · ${activeCounts.partial} आंशिक · ${activeCounts.ne} पात्र नहीं`
          : `${activeCounts.total} trials checked · ${activeCounts.pe} Potentially Eligible · ${activeCounts.partial} Partially · ${activeCounts.ne} Not Eligible`}
      </p>

      {dlErr && <Banner kind="error">{dlErr}</Banner>}
      <div style={{ maxHeight: 460, overflow: "auto",
                    border: "1px solid rgba(128,128,128,.3)", borderRadius: 8, marginTop: "0.25rem" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.82rem" }}>
          <thead>
            <tr>
              {[...columns, ...(onOpen ? [""] : [])].map((h, i) => (
                <th key={i} style={TH}>{h ? label(h) : ""}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map(({ pid, t }) => (
              <tr key={`${pid}-${t.trial_id}`} style={{ borderBottom: "1px solid rgba(128,128,128,.18)" }}>
                {showAll && (
                  <td style={{ ...TD, fontWeight: 600, whiteSpace: "nowrap" }}>{pid}</td>
                )}
                <td style={TD}>{t.trial_id}</td>
                <td style={{ ...TD, maxWidth: 320 }}>
                  <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
                       title={t.title}>{t.title}</div>
                </td>
                <td style={TD}><EligibilityBadge status={t.eligibility} hi={hi} /></td>
                <td style={{ ...TD, fontWeight: 600, color: verdictColor(t.eligibility), whiteSpace: "nowrap" }}>
                  {t.match_percent ?? Math.round((t.similarity_score || 0) * 100)}%
                </td>
                <td style={TD}>{t.phase}</td>
                <td style={{ ...TD, maxWidth: 300, color: "rgba(128,128,128,1)" }}>
                  <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
                       title={[...(t.reasons_for || []), ...(t.reasons_against || []),
                               ...(t.failed_criteria || [])].join("  |  ")}>
                    {hi
                      ? (t.reasons_for || [])[0] || (t.reasons_against || [])[0]
                        || (t.missing_information || [])[0] || "—"
                      : (t.reasons_for || []).slice(0, 2).join("; ")
                        || (t.reasons_against || [])[0]
                        || (t.missing_information || [])[0]
                        || "—"}
                  </div>
                </td>
                {onOpen && (
                  <td style={TD}>
                    <button type="button" className="btn secondary"
                      style={{ padding: "0.2rem 0.6rem", fontSize: "0.78rem" }}
                      onClick={() => onOpen(pid)}>
                      {hi ? "खोलें" : "Open"}
                    </button>
                  </td>
                )}
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={columns.length + (onOpen ? 1 : 0)}
                    style={{ padding: "0.9rem", textAlign: "center", color: "rgba(128,128,128,1)" }}>
                  {onlyEligible
                    ? (hi ? "कोई पूर्ण पात्र पंक्ति नहीं — सभी जाँच देखने के लिए फ़िल्टर हटाएँ।"
                          : "No Potentially Eligible rows — untick the filter to see every check.")
                    : (hi ? "कोई परिणाम पंक्ति नहीं।" : "No result rows.")}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
