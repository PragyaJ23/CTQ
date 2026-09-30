import { useRef, useState } from "react";
import {
  extractDocument, uploadLabels, runEvaluation, getEvaluationSample, apiErrorMessage,
} from "../services/api.js";
import { Banner, Loading } from "../components/ui.jsx";

function MetricTile({ label, value }) {
  return (
    <div className="metric-tile">
      <div className="metric-value">{value}</div>
      <div className="metric-label">{label}</div>
    </div>
  );
}

function ConfusionMatrix({ c }) {
  const cells = [
    { key: "TP", cls: "tp", desc: "Eligible correctly identified" },
    { key: "FN", cls: "fn", desc: "Eligible missed - predicted Not Eligible" },
    { key: "FP", cls: "fp", desc: "Unsafe error - predicted Eligible but was not" },
    { key: "TN", cls: "tn", desc: "Not Eligible correctly identified" },
  ];
  return (
    <div>
      <div className="cm-grid" role="table" aria-label="Confusion matrix">
        <div />
        <div className="cm-header">Actual: Eligible</div>
        <div className="cm-header">Actual: Not Eligible</div>
        <div className="cm-row-label">Predicted: Eligible</div>
        {cells.slice(0, 2).map((cell) => (
          <div key={cell.key} className={`cm-cell ${cell.cls}`} title={cell.desc}>
            <span className="num">{c[cell.key]}</span>
            <span className="lab">{cell.key}</span>
          </div>
        ))}
        <div className="cm-row-label">Predicted: Not Eligible</div>
        {cells.slice(2).map((cell) => (
          <div key={cell.key} className={`cm-cell ${cell.cls}`} title={cell.desc}>
            <span className="num">{c[cell.key]}</span>
            <span className="lab">{cell.key}</span>
          </div>
        ))}
      </div>
      <p className="hint" style={{ marginTop: "0.6rem" }}>
        TP = true positive, FP = false positive, FN = false negative, TN = true negative.
        Rows where the model answered "Partially Eligible" are excluded from the binary
        matrix and reported separately.
      </p>
    </div>
  );
}

function downloadText(content, filename, type = "text/csv") {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

const pct = (v) => (v == null ? "-" : `${(v * 100).toFixed(1)}%`);

export default function Evaluation() {
  const [unstructured, setUnstructured] = useState(null);   // {patients:[...]}
  const [unstructInfo, setUnstructInfo] = useState(null);   // preview info
  const [labelInfo, setLabelInfo] = useState(null);
  const [rankScope, setRankScope] = useState("all");        // "all" | "top5" | "top10" ...
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const unstructRef = useRef(null);
  const labelRef = useRef(null);

  /** Unstructured upload: parse via the document reader (no extraction yet). */
  const handleUnstructured = async (file) => {
    if (!file) return;
    setError(""); setResult(null); setBusy(`Reading “${file.name}”...`);
    try {
      const res = await extractDocument(file);
      // Send BOTH the raw text and the facts the upload already extracted -
      // analyze-batch then skips the second (slow) ML NER pass entirely.
      setUnstructured({
        patients: res.results.map((r) => ({
          patient_id: r.note_id, text: r.text, extracted_facts: r.facts,
        })),
      });
      setUnstructInfo({ name: file.name, kind: res.kind, count: res.count });
    } catch (err) {
      setUnstructured(null);
      if (unstructRef.current) unstructRef.current.value = "";
      setError(apiErrorMessage(err));
    } finally {
      setBusy("");
    }
  };

  const handleLabels = async (file) => {
    if (!file) return;
    setError(""); setBusy("Validating label file...");
    try {
      const info = await uploadLabels(file);
      setLabelInfo({ ...info, name: file.name });
      if (info.invalid_rows?.length) {
        setError(`Some label rows were skipped: ${info.invalid_rows.slice(0, 3).join("; ")}${info.invalid_rows.length > 3 ? " ..." : ""}`);
      }
    } catch (err) {
      setLabelInfo(null);
      if (labelRef.current) labelRef.current.value = "";
      setError(apiErrorMessage(err));
    } finally {
      setBusy("");
    }
  };

  const run = async () => {
    setBusy("ML NER is converting each unstructured patient into a structured profile, checking every trial, then scoring against the labelled data...");
    setError("");
    try {
      const res = await runEvaluation(unstructured.patients, labelInfo.labels,
                                      rankScope === "all" ? null : Number(rankScope.replace("top", "")));
      setResult(res);
      window.scrollTo(0, 0);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setBusy("");
    }
  };

  /** One click: the synthetic notes + ground-truth labels bundled with the app. */
  const loadSample = async () => {
    setError(""); setResult(null);
    setBusy("Loading the bundled sample patients and labels...");
    try {
      const sample = await getEvaluationSample();
      setUnstructured({ patients: sample.patients });
      setUnstructInfo({ name: sample.files?.patients || "bundled sample",
                        kind: "sample", count: sample.patients.length });
      setLabelInfo({ count: sample.labels.length, labels: sample.labels,
                     name: sample.files?.labels || "bundled labels" });
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setBusy("");
    }
  };

  const downloadPredictions = () => {
    const header = "patient_id,trial_id,predicted,actual\n";
    const lines = result.rows.map((r) => `${r.patient_id},${r.trial_id},"${r.predicted}","${r.actual}"`).join("\n");
    downloadText(header + lines, "evaluation_predictions.csv");
  };

  return (
    <div>
      <h1>Model Evaluation</h1>
      <p style={{ color: "var(--muted)" }}>
        Give <strong>unstructured patient data</strong> (notes / summaries / CSV of medical history)
        plus <strong>labelled structured data</strong> (ground truth). The ML NER converts each
        unstructured patient into a structured profile, every trial in the database is checked, and
        the predictions are scored against your labels: accuracy, precision, recall, F1 and the
        confusion matrix.
      </p>

      {error && <Banner kind="error">{error}</Banner>}

      <div className="card section-gap">
        <h3>Sample data</h3>
        <p className="hint">
          No files handy? Load the synthetic sample set shipped with the app: 10 patient notes
          plus 17 labelled patient/trial pairs. Then just press <strong>Run Evaluation</strong>.
        </p>
        <button type="button" className="btn" onClick={loadSample} disabled={!!busy}>
          Load bundled sample data (10 patients, 17 labels)
        </button>
      </div>

      <div className="card section-gap">
        <h3>1 · Unstructured patient data * (PDF / photo / CSV / Excel / TXT / JSON)</h3>
        <p className="hint">
          A file with clinical notes per patient — e.g. columns like <span className="mono">patient_id, notes</span>{" "}
          (CSV), one note per line (TXT), or a document of medical history. Accepted formats:{" "}
          <span className="mono">.pdf .png .jpg .jpeg .csv .xlsx .tsv .txt .json</span>
        </p>
        <input ref={unstructRef} type="file"
          accept=".pdf,.png,.jpg,.jpeg,.bmp,.webp,.csv,.xlsx,.xls,.tsv,.txt,.json"
          disabled={!!busy}
          onChange={(e) => handleUnstructured(e.target.files?.[0])} />
        {unstructInfo && (
          <Banner kind="success">
            Loaded <strong>{unstructInfo.count}</strong> patient {unstructInfo.count === 1 ? "note" : "notes"} from{" "}
            <strong>{unstructInfo.name}</strong> ({unstructInfo.kind}).
          </Banner>
        )}
      </div>

      <div className="card">
        <h3>2 · Labelled structured data * (ground truth)</h3>
        <p className="hint">
          CSV with columns <span className="mono">patient_id, trial_id, actual_label</span> — actual_label:
          1 = Potentially Eligible, 0 = Not Eligible, 2 = Partially Eligible.
        </p>
        <input ref={labelRef} type="file" accept=".csv,.json,.txt,.tsv,.xlsx,.xls" disabled={!!busy}
          onChange={(e) => handleLabels(e.target.files?.[0])} />
        {labelInfo && (
          <Banner kind="success">
            Loaded <strong>{labelInfo.count}</strong> labels from <strong>{labelInfo.name}</strong>.
          </Banner>
        )}
      </div>

      <div className="card">
        <h3>3 · Ranking scope</h3>
        <p className="hint">
          Which trials should accuracy be scored against? <strong>All trials</strong> checks every
          trial in the database. <strong>Top-K</strong> scores only each patient's K best-matching
          trials (by match score) — the way a coordinator actually reads the ranked list. Labelled
          pairs that fall outside a patient's top-K are skipped and reported.
        </p>
        <div className="btn-row">
          {["all", "top3", "top5", "top10"].map((s) => (
            <button key={s} type="button"
              className={`btn ${rankScope === s ? "primary" : ""}`}
              onClick={() => setRankScope(s)}>
              {s === "all" ? "All trials" : s === "top3" ? "Top 3 trials" : s === "top5" ? "Top 5 trials" : "Top 10 trials"}
            </button>
          ))}
        </div>
      </div>

      <div className="card">
        <h3>4 · Run evaluation</h3>
        <button className="btn primary" onClick={run}
          disabled={!unstructured || !labelInfo || !!busy}>
          Run Evaluation
        </button>
        {(!unstructured || !labelInfo) && (
          <span className="hint" style={{ marginLeft: "0.6rem" }}>
            Upload both files to enable evaluation.
          </span>
        )}
        {busy && <Loading text={busy} />}
      </div>

      {result && (
        <>
          <h2 className="section-gap">Evaluation Dashboard</h2>
          <div className="metric-tiles">
            <MetricTile label="Patients evaluated" value={result.patients_evaluated} />
            <MetricTile label="Labelled pairs" value={result.pairs_labelled} />
            <MetricTile label="Accuracy" value={pct(result.metrics.accuracy)} />
            <MetricTile label="Precision" value={pct(result.metrics.precision)} />
            <MetricTile label="Recall" value={pct(result.metrics.recall)} />
            <MetricTile label="F1 score" value={pct(result.metrics.f1)} />
          </div>

          <div className="card section-gap">
            <h3>Confusion Matrix</h3>
            {(result.ranking_scope || "all trials") !== "all trials" && (
              <p className="hint">
                Scope: <strong>{result.ranking_scope}</strong> · {result.skipped_outside_top_k} labelled
                pair(s) skipped for falling outside the ranked scope.
              </p>
            )}
            <ConfusionMatrix c={result.metrics.confusion} />
          </div>

          {result.extraction_log?.length > 0 && (
            <details className="card section-gap">
              <summary style={{ cursor: "pointer", fontWeight: 600 }}>
                ML extraction details ({result.extraction_log.length} patients)
              </summary>
              {result.extraction_log.map((e) => (
                <div key={e.patient_id} style={{ margin: "0.5rem 0" }}>
                  <strong className="mono">{e.patient_id}</strong>{" "}
                  <span className="hint">{JSON.stringify(e.facts)}</span>
                </div>
              ))}
            </details>
          )}

          <div className="card section-gap">
            <h3>Predictions vs labels</h3>
            <div className="table-wrap">
              <table className="data">
                <thead><tr><th>Patient</th><th>Trial</th><th>Predicted</th><th>Actual</th><th>Match</th></tr></thead>
                <tbody>
                  {result.rows.map((r, i) => (
                    <tr key={i}>
                      <td className="mono">{r.patient_id}</td>
                      <td className="mono">{r.trial_id}</td>
                      <td>{r.predicted}</td>
                      <td>{r.actual === "Potentially Eligible" ? "Eligible" : r.actual === "Not Eligible" ? "Not Eligible" : r.actual}</td>
                      <td>{r.predicted === r.actual ? "✓" : "✗"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <button className="btn" style={{ marginTop: "0.7rem" }} onClick={downloadPredictions}>
              ⤓ Download results (CSV)
            </button>
          </div>
        </>
      )}
    </div>
  );
}
