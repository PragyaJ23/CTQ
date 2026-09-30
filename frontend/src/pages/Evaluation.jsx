import { useRef, useState } from "react";
import {
  extractDocument, uploadLabels, runEvaluation, getEvaluationSample, apiErrorMessage,
  calibrateThresholds, getThresholds,
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

/** Minimal inline SVG curve with an optional operating-point dot [x, y]. */
function CurveBlock({ title, x, y, xs, ys, dot }) {
  if (!xs || !ys || xs.length < 2) return null;
  const W = 420, H = 200, PAD = 34;
  const pts = xs.map((v, i) => [v, ys[Math.min(i, ys.length - 1)]]);
  const px = (v) => PAD + v * (W - PAD - 8);
  const py = (v) => H - PAD - v * (H - PAD - 10);
  const path = pts.map(([a, b], i) => `${i ? "L" : "M"}${px(a).toFixed(1)},${py(b).toFixed(1)}`).join(" ");
  return (
    <div style={{ display: "inline-block", margin: "0.5rem 1rem 0.5rem 0", textAlign: "center" }}>
      <svg width={W} height={H} style={{ background: "rgba(128,128,128,.06)", borderRadius: 8 }}>
        <path d={path} fill="none" stroke="#1F4E78" strokeWidth="2" />
        {dot && <circle cx={px(dot[0])} cy={py(dot[1])} r="4" fill="#b02a37" />}
        <text x={PAD} y={14} fontSize="11" fill="rgba(128,128,128,1)">{title}</text>
        <text x={W / 2} y={H - 8} fontSize="10" textAnchor="middle" fill="rgba(128,128,128,1)">{x}</text>
        <text x={10} y={H / 2} fontSize="10" transform={`rotate(-90 10 ${H / 2})`}
          textAnchor="middle" fill="rgba(128,128,128,1)">{y}</text>
      </svg>
    </div>
  );
}

function ThresholdCalibration() {
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [cal, setCal] = useState(null);

  const run = async () => {
    setBusy("Scoring 1600 labelled pairs and sweeping thresholds...");
    setError("");
    try {
      setCal(await calibrateThresholds());
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setBusy("");
    }
  };

  const load = async () => {
    setError("");
    try {
      const r = await getThresholds();
      if (r.thresholds) setCal(r.thresholds);
      else setError("No saved calibration yet - press Calibrate.");
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  };

  const fp = cal?.f1_point?.best;
  const ap = cal?.accuracy_point?.best;
  return (
    <div className="card section-gap">
      <h3>Similarity threshold calibration</h3>
      <p className="hint">
        Scores every labelled patient-trial pair ({cal?.pairs_used || 1600} pairs) with the production
        embedder and picks the thresholds that maximise F1 and accuracy - precision, recall, F1 and
        accuracy at every candidate cut, plus PR/ROC curve analysis. The F1-optimal cut is saved and
        used by the matching engine to upgrade high-similarity partial profiles to Potentially
        Eligible.
      </p>
      <div className="btn-row">
        <button type="button" className="btn primary" onClick={run} disabled={!!busy}>
          Calibrate thresholds on labelled data
        </button>
        <button type="button" className="btn" onClick={load} disabled={!!busy}>
          Load saved calibration
        </button>
      </div>
      {busy && <Loading text={busy} />}
      {error && <Banner kind="error">{error}</Banner>}
      {cal && (
        <div className="section-gap">
          <div className="metric-tiles">
            <MetricTile label="Threshold (F1-optimal)" value={cal.potentially?.toFixed(3) ?? "-"} />
            <MetricTile label="F1 @ threshold" value={fp ? fp.f1.toFixed(3) : "-"} />
            <MetricTile label="Precision @ threshold" value={fp ? pct(fp.precision) : "-"} />
            <MetricTile label="Recall @ threshold" value={fp ? pct(fp.recall) : "-"} />
            <MetricTile label="Accuracy @ threshold" value={fp ? pct(fp.accuracy) : "-"} />
            <MetricTile label="Accuracy-optimal cut" value={ap ? ap.threshold.toFixed(3) : "-"} />
            <MetricTile label="ROC AUC" value={cal.f1_point?.roc_auc?.toFixed(3) ?? "-"} />
            <MetricTile label="Avg precision (PR AUC)" value={cal.f1_point?.average_precision?.toFixed(3) ?? "-"} />
          </div>
          <CurveBlock title="Precision-Recall curve" x="recall" y="precision"
            xs={cal.f1_point?.pr_curve?.recall} ys={cal.f1_point?.pr_curve?.precision}
            dot={fp ? [fp.recall, fp.precision] : null} />
          <CurveBlock title="ROC curve" x="fpr" y="tpr"
            xs={cal.f1_point?.roc_curve?.fpr} ys={cal.f1_point?.roc_curve?.tpr} />
          <p className="hint">
            Calibrated {cal.calibrated_at} · {cal.pairs_used} pairs ({cal.positives} eligible / {cal.negatives} not)
            · {cal.patients} patients × {cal.trials} trials · {cal.seconds}s. Mean similarity:
            eligible {cal.score_stats?.mean_positive}, not-eligible {cal.score_stats?.mean_negative}.
          </p>
        </div>
      )}
    </div>
  );
}

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

      <ThresholdCalibration />

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
