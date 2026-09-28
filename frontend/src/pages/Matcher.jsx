import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  analyzePatient, analyzeCohort, exportCohortExcel, buildPayload, extractDocument,
  uploadPatients, apiErrorMessage,
} from "../services/api.js";
import { Banner, Loading, EligibilityBadge, MatchScore, MetaChip } from "../components/ui.jsx";

const COMORBIDITIES = [
  "Diabetes", "Hypertension", "Cardiovascular disease", "Kidney disease", "Liver disease",
  "Cancer", "Asthma", "COPD", "Thyroid disease", "Autoimmune disease", "Infectious diseases", "Other",
];

const SYMPTOMS = [
  "Increased thirst", "Frequent urination", "Fatigue", "Blurred vision", "Numbness in feet",
  "Slow healing wounds", "Headache", "Dizziness", "Shortness of breath", "Chest pain",
  "Joint pain", "Fever", "Cough", "Weight loss",
];

const YES_NO = ["Yes", "No", "Unknown"];

/** One-click demo profiles (synthetic data). */
const SAMPLE_PATIENTS = [
  {
    key: "t2dm",
    label: "Sample: Diabetes (47F)",
    values: {
      patient_id: "DEMO-47", age: "47", gender: "Female", state: "West Bengal", city: "Kolkata",
      condition: "Type 2 Diabetes", disease_duration_months: "24",
      height_cm: "162", weight_kg: "78", hba1c: "8.2", systolic_bp: "138", diastolic_bp: "86",
      pregnancy_status: "Not Pregnant", smoking_status: "Never", alcohol_use: "Occasional",
    },
    comorbidities: ["Diabetes", "Hypertension"],
    meds: [{ name: "Metformin", dose: "500 mg", frequency: "twice daily", duration_months: "12" },
           { name: "Glimepiride", dose: "1 mg", frequency: "once daily", duration_months: "6" }],
  },
  {
    key: "htn",
    label: "Sample: Hypertension (58M)",
    values: {
      patient_id: "DEMO-58", age: "58", gender: "Male", state: "Maharashtra", city: "Pune",
      condition: "Hypertension", disease_duration_months: "30", disease_severity: "Moderate",
      height_cm: "172", weight_kg: "84", systolic_bp: "158", diastolic_bp: "96",
      smoking_status: "Former", alcohol_use: "Occasional",
    },
    comorbidities: ["Hypertension"],
    meds: [{ name: "Amlodipine", dose: "5 mg", frequency: "once daily", duration_months: "24" }],
  },
  {
    key: "asthma",
    label: "Sample: Asthma (24F)",
    values: {
      patient_id: "DEMO-24", age: "24", gender: "Female", state: "Karnataka", city: "Bengaluru",
      condition: "Asthma", disease_duration_months: "36", disease_severity: "Mild",
      height_cm: "158", weight_kg: "55", pregnancy_status: "Not Pregnant", smoking_status: "Never",
    },
    comorbidities: ["Asthma"],
    meds: [{ name: "Salbutamol inhaler", dose: "100 mcg", frequency: "as needed", duration_months: "12" }],
  },
  {
    key: "healthy",
    label: "Sample: Healthy volunteer (28M)",
    values: {
      patient_id: "DEMO-28", age: "28", gender: "Male", state: "Delhi", city: "New Delhi",
      height_cm: "175", weight_kg: "70", smoking_status: "Never", alcohol_use: "Never",
      prior_trial_participation: "No",
    },
    comorbidities: [],
    meds: [],
  },
];

const EMPTY_FORM = {
  patient_id: "", age: "", gender: "", state: "", city: "", height_cm: "", weight_kg: "",
  condition: "", disease_duration_months: "", disease_severity: "", previous_diagnosis: "",
  other_medical_history: "", treatment_failure: "Unknown", drug_allergies: "",
  hba1c: "", fasting_glucose: "", systolic_bp: "", diastolic_bp: "", creatinine: "", egfr: "",
  hemoglobin: "", wbc: "", platelets: "", alt: "", ast: "", bilirubin: "", cholesterol: "",
  fev1_percent: "",
  pregnancy_status: "", smoking_status: "", alcohol_use: "", prior_trial_participation: "Unknown",
  surgery_history: "", infection_history: "", organ_function_notes: "",
};

function Field({ label, hint, children, wide }) {
  return (
    <div className={`field ${wide ? "wide" : ""}`}>
      <label>{label}</label>
      {children}
      {hint && <span className="hint">{hint}</span>}
    </div>
  );
}

function MCQ({ value, onChange }) {
  return (
    <div className="mcq-row">
      {YES_NO.map((opt) => (
        <button type="button" key={opt}
          className={`mcq ${value === opt ? "selected" : ""}`}
          onClick={() => onChange(opt)}>{opt}</button>
      ))}
    </div>
  );
}

/** Shared "how many trials to check" picker (used by every tab's submit path). */
const TRIAL_SCOPES = [
  { value: "all", label: "All trials" },
  { value: "5", label: "Top 5" },
  { value: "10", label: "Top 10" },
  { value: "15", label: "Top 15" },
];
function TrialScopePicker({ value, onChange }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
      <span style={{ fontWeight: 600, fontSize: "0.85rem" }}>Trials to check:</span>
      <div className="mcq-row">
        {TRIAL_SCOPES.map((s) => (
          <button type="button" key={s.value}
            className={`mcq ${value === s.value ? "selected" : ""}`}
            onClick={() => onChange(s.value)}>{s.label}</button>
        ))}
      </div>
    </div>
  );
}

/** Flatten ML-NER facts into the same payload shape the structured form sends. */
function noteToFactsPayload(facts, noteId) {
  const labs = facts.labs || {};
  const meds = (facts.current_medications || []).map((m) => ({
    name: m.name, dose: m.dose, frequency: m.frequency,
  }));
  return {
    patient_id: noteId,
    age: facts.age, gender: facts.gender, condition: facts.condition,
    disease_duration_months: facts.disease_duration_months,
    symptoms: facts.symptoms || [],
    current_medications: meds,
    comorbidities: facts.comorbidities || {},
    smoking_status: facts.smoking_status, alcohol_use: facts.alcohol_use,
    pregnancy_status: facts.pregnancy_status,
    height_cm: facts.height_cm, weight_kg: facts.weight_kg,
    ...labs,
  };
}

/** Lab field names that may sit flat on a payload (shown as chips). */
const LAB_KEYS = new Set([
  "hba1c", "fasting_glucose", "systolic_bp", "diastolic_bp", "creatinine", "egfr",
  "hemoglobin", "wbc", "platelets", "alt", "ast", "bilirubin", "cholesterol", "fev1_percent",
]);

/** Human-readable chips for a flat payload (shared by all tabs). */
function fmtFacts(facts) {
  const bits = [];
  if (facts.age) bits.push(`Age ${facts.age}`);
  if (facts.gender) bits.push(facts.gender);
  if (facts.condition) bits.push(facts.condition);
  if (facts.disease_duration_months) bits.push(`${facts.disease_duration_months} mo`);
  if (facts.smoking_status) bits.push(`Smoke: ${facts.smoking_status}`);
  if (facts.alcohol_use) bits.push(`Alcohol: ${facts.alcohol_use}`);
  if (facts.pregnancy_status) bits.push(facts.pregnancy_status);
  const meds = (facts.current_medications || []).map((m) =>
    m.name + (m.dose ? ` ${m.dose}` : "") + (m.frequency ? ` (${m.frequency})` : ""));
  const labs = facts.labs
    ? Object.entries(facts.labs).map(([k, v]) => `${k} ${v}`)
    : Object.entries(facts).filter(([k]) => LAB_KEYS.has(k)).map(([k, v]) => `${k} ${v}`);
  const symptoms = facts.symptoms || [];
  return [...bits, ...meds, ...symptoms, ...labs];
}

/** Backend profile -> form/cohort row (strings for inputs, objects kept). */
function profileToForm(p) {
  const out = {};
  for (const [k, v] of Object.entries(p)) {
    if (v === null || v === undefined) continue;
    out[k] = typeof v === "object" ? v : String(v);
  }
  return out;
}

/** Shared per-patient viewer for "Results for all patients" (any tab). */
function AllResultsViewer({ allResult, allActive, setAllActive }) {
  const navigate = useNavigate();
  const ok = allResult.results.filter((r) => r.ok);
  const failed = allResult.results.filter((r) => !r.ok);
  const active = ok[allActive];
  if (!active) return <Banner kind="warn">No patient results available.</Banner>;
  const trials = active.response?.results || [];
  const counts = trials.reduce((acc, t) => {
    acc[t.eligibility] = (acc[t.eligibility] || 0) + 1; return acc;
  }, {});
  return (
    <div className="section-gap">
      <h2>Results for all patients</h2>
      <Banner kind={failed.length === 0 ? "success" : "warn"}>
        {ok.length} of {allResult.results.length} patients analysed
        {failed.length > 0 && <> · failed: {failed.map((f) => f.patient_id).join(", ")}</>}
      </Banner>
      <div className="card section-gap">
        <div className="btn-row" style={{ flexWrap: "wrap", marginBottom: "0.6rem" }}>
          {ok.map((r, i) => (
            <button key={r.patient_id} type="button"
              className={`btn ${i === allActive ? "primary" : ""}`}
              style={{ padding: "0.35rem 0.9rem" }}
              onClick={() => setAllActive(i)}>
              {r.patient_id}
            </button>
          ))}
        </div>
        <div className="btn-row" style={{ marginBottom: "0.6rem" }}>
          <button type="button" className="btn secondary" disabled={allActive === 0}
            onClick={() => setAllActive((i) => Math.max(0, i - 1))}>
            ← Previous patient
          </button>
          <span style={{ fontWeight: 600 }}>Patient {allActive + 1} of {ok.length}</span>
          <button type="button" className="btn secondary"
            disabled={allActive >= ok.length - 1}
            onClick={() => setAllActive((i) => Math.min(ok.length - 1, i + 1))}>
            Next patient →
          </button>
          <button type="button" className="btn"
            onClick={() => {
              sessionStorage.setItem("ctq_results", JSON.stringify(
                { response: active.response, profile: {} }));
              navigate("/results");
            }}>
            Open full page view for {active.patient_id}
          </button>
        </div>
        <h3>Trials for {active.patient_id} — {trials.length} checked</h3>
        <p className="hint" style={{ margin: "0.2rem 0 0.6rem" }}>
          {Object.entries(counts).map(([k, v]) => `${v} ${k}`).join(" · ")}
        </p>
        {trials.map((t) => (
          <div key={t.trial_id}
            className={`result-card section-gap ${t.eligibility === "Potentially Eligible" ? "eligible" : t.eligibility === "Not Eligible" ? "not-eligible" : "insufficient"}`}
            style={{ padding: "0.8rem 1rem" }}>
            <div className="result-head">
              <div>
                <div className="trial-id">{t.trial_id}</div>
                <div className="result-title">{t.title}</div>
              </div>
            </div>
            <div className="result-meta">
              <EligibilityBadge status={t.eligibility} />
              <MatchScore percent={t.match_percent ?? Math.round((t.similarity_score || 0) * 100)}
                similarity={t.similarity_score} />
              <MetaChip>{t.condition}</MetaChip>
              <MetaChip>{t.status}</MetaChip>
            </div>
            {t.reasons_for?.length > 0 && (
              <ul className="hint" style={{ margin: "0.4rem 0 0" }}>
                {t.reasons_for.slice(0, 3).map((x, i) => <li key={i}>{x}</li>)}
              </ul>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

/** Unstructured panel: notes/photo/PDF -> ML NER -> matching. */
function UnstructuredPanel() {
  const navigate = useNavigate();
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [extracted, setExtracted] = useState(null);
  const [activeNote, setActiveNote] = useState(0);
  const [allResult, setAllResult] = useState(null);
  const [allActive, setAllActive] = useState(0);
  const [trialScope, setTrialScope] = useState("all");
  const topK = trialScope === "all" ? null : Number(trialScope);
  const fileRef = useRef(null);

  const handleFile = async (file) => {
    if (!file) return;
    setError("");
    setExtracted(null);
    setBusy(`Reading “${file.name}” and extracting entities with the ML NER...`);
    try {
      const res = await extractDocument(file);
      setExtracted(res);
      setActiveNote(0);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setBusy("");
    }
  };

  const downloadCsv = () => {
    const blob = new Blob([extracted.csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "unstructured_extracted_results.csv"; a.click();
    URL.revokeObjectURL(url);
  };

  const analyzeNote = async (facts, noteId) => {
    setBusy(topK ? `Matching the extracted profile against the top ${topK} best-matching trials...`
                 : "Matching the extracted profile against every trial in the database...");
    setError("");
    try {
      const payload = noteToFactsPayload(facts, noteId);
      const response = await analyzePatient(payload, topK);
      sessionStorage.setItem("ctq_results", JSON.stringify({ response, profile: payload }));
      navigate("/results");
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setBusy("");
    }
  };

  /** ALL patients at once: reuse the structured cohort endpoint, then browse
   *  the in-page per-patient viewer exactly like the structured cohort. */
  const analyzeAllNotes = async () => {
    setBusy(topK ? `Checking the top ${topK} best-matching trials for all ${extracted.results.length} patients...`
                 : `Checking every trial in the database for all ${extracted.results.length} patients...`);
    setError("");
    try {
      const built = extracted.results.map((r) => noteToFactsPayload(r.facts, r.note_id));
      const res = await analyzeCohort(built, topK);
      setAllResult(res);
      setAllActive(0);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setBusy("");
    }
  };

  return (
    <div className="card section-gap">
      <h2>Unstructured patient data</h2>
      <p className="hint">
        Upload a photo of a prescription or discharge summary (JPG/PNG), a PDF, or a CSV/Excel/TXT
        file of medical history. The DistilBERT ML NER reads the text, converts it into structured
        profile fields, and every trial in the database is checked.
      </p>
      <input ref={fileRef} type="file" accept=".pdf,.png,.jpg,.jpeg,.bmp,.webp,.csv,.xlsx,.xls,.tsv,.txt,.json"
        disabled={!!busy}
        onChange={(e) => handleFile(e.target.files?.[0])} />
      {busy && <Loading text={busy} />}
      {error && <Banner kind="error">{error}</Banner>}

      {extracted && (
        <div className="section-gap">
          <Banner kind="success">
            Extracted structured data from <strong>{extracted.count}</strong>
            {extracted.count === 1 ? " note" : " notes"} in “{extracted.filename}” ({extracted.kind}).
          </Banner>
          {extracted.results.some((r) => r.translated) && (
            <Banner kind="warn">
              🌐 {extracted.results.filter((r) => r.translated).length} of {extracted.results.length} note(s)
              were in a non-English script and were auto-translated to English before ML extraction
              ({[...new Set(extracted.results.filter((r) => r.translated).map((r) => r.source_script))].join(", ")}).
            </Banner>
          )}
          {extracted.results.some((r) => r.source_script && !r.translated) && (
            <Banner kind="warn">
              ⚠ {extracted.results.filter((r) => r.source_script && !r.translated).length} note(s) are in a
              non-English script but could not be translated (no LLM key / rate-limited) — extraction ran on
              the untranslated text, so only Latin-script lab values may have been found.
            </Banner>
          )}
          {(() => {
            const r = extracted.results[activeNote];
            if (!r) return null;
            return (
              <div className="card section-gap" style={{ padding: "0.9rem 1.1rem" }}>
                <div className="result-head" style={{ marginBottom: "0.2rem" }}>
                  <div style={{ fontWeight: 600 }}>{r.note_id}</div>
                  <span className="hint">Patient {activeNote + 1} of {extracted.results.length}</span>
                </div>
                <div className="chip-row" style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem", margin: "0.5rem 0" }}>
                  {fmtFacts(r.facts).map((x, i) => (
                    <span key={i} className="meta-chip">{x}</span>
                  ))}
                  {fmtFacts(r.facts).length === 0 && <span className="hint">No entities extracted from this note.</span>}
                </div>
                <div className="btn-row" style={{ flexWrap: "wrap", alignItems: "center" }}>
                  <TrialScopePicker value={trialScope} onChange={setTrialScope} />
                </div>
                <div className="btn-row">
                  <button className="btn primary" disabled={!!busy} onClick={() => analyzeNote(r.facts, r.note_id)}>
                    Find Matching Trials for this profile
                  </button>
                  {extracted.results.length > 1 && (
                    <button className="btn" disabled={!!busy} onClick={analyzeAllNotes}>
                      Find Trials for all {extracted.results.length} patients
                    </button>
                  )}
                </div>
              </div>
            );
          })()}
          {extracted.results.length > 1 && (
            <div className="btn-row section-gap" style={{ justifyContent: "center", alignItems: "center" }}>
              <button className="btn secondary" disabled={activeNote === 0}
                onClick={() => setActiveNote((i) => Math.max(0, i - 1))}>
                ← Previous patient
              </button>
              <span style={{ fontWeight: 600 }}>
                Patient {activeNote + 1} / {extracted.results.length}
              </span>
              <button className="btn secondary" disabled={activeNote >= extracted.results.length - 1}
                onClick={() => setActiveNote((i) => Math.min(extracted.results.length - 1, i + 1))}>
                Next patient →
              </button>
            </div>
          )}
          <div className="btn-row">
            <button className="btn" onClick={downloadCsv}>⤓ Download extracted results (CSV)</button>
          </div>
        </div>
      )}

      {allResult && (
        <AllResultsViewer allResult={allResult} allActive={allActive} setAllActive={setAllActive} />
      )}
    </div>
  );
}

export default function Matcher() {
  const navigate = useNavigate();
  const [tab, setTab] = useState("structured");
  const [form, setForm] = useState(EMPTY_FORM);
  const [comorbidities, setComorbidities] = useState({});
  const [symptoms, setSymptoms] = useState([]);
  const [symptomOther, setSymptomOther] = useState("");
  const [meds, setMeds] = useState([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [cohort, setCohort] = useState([]);
  const [cohortBusy, setCohortBusy] = useState("");
  const [cohortResult, setCohortResult] = useState(null);
  const [activeCohort, setActiveCohort] = useState(0);
  const [trialScope, setTrialScope] = useState("all");   // "all" | "5" | "10" | "15"

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  /** Fill the form with a one-click sample profile. */
  const loadSample = (s) => {
    setForm((f) => ({ ...EMPTY_FORM, ...s.values }));
    const comorb = {};
    for (const c of COMORBIDITIES) comorb[c] = s.comorbidities.includes(c) ? "Yes" : "No";
    setComorbidities(comorb);
    setMeds(s.meds.map((m) => ({ ...m })));
    setSymptoms([]);
    setSymptomOther("");
    window.scrollTo(0, 0);
  };

  const addPatient = () => {
    setCohort((list) => {
      const blank = { ...EMPTY_FORM,
        patient_id: `P${String(list.length + 2).padStart(3, "0")}` };
      return [...list, blank];
    });
  };

  const removePatient = (i) => setCohort((list) => list.filter((_, j) => j !== i));

  /** Load a structured patient CSV into the form + cohort rows.
   *  The main form's meds/symptoms/comorbidities live in SEPARATE state
   *  (meds, symptoms, comorbidities) and are read from there on submit -
   *  so row 1 of the CSV must populate those states too, not just `form`. */
  const csvFileRef = useRef(null);
  const [csvMsg, setCsvMsg] = useState("");
  const handleStructuredCsv = async (file) => {
    if (!file) return;
    setError(""); setCsvMsg("");
    try {
      const res = await uploadPatients(file);
      const list = res.patients || [];
      if (list.length === 0) throw new Error("No patients found in that file.");
      const rows = list.map(profileToForm);
      const [first, ...rest] = rows;
      // Row 1's meds/symptoms/comorbidities live in DEDICATED states (the form
      // inputs + submit paths read from there), so keep them out of `form` to
      // avoid a second, stale copy of the same data.
      const { current_medications, symptoms: rowSymptoms, comorbidities: rowComorb,
              ...formFields } = first;
      setForm((f) => ({ ...f, ...formFields }));
      setMeds(Array.isArray(current_medications)
        ? current_medications.map((m) => ({
            name: m?.name || "", dose: m?.dose || "",
            frequency: m?.frequency || "", duration_months: m?.duration_months ?? "",
          }))
        : []);
      setSymptoms(Array.isArray(rowSymptoms)
        ? rowSymptoms.filter((s) => typeof s === "string") : []);
      setSymptomOther("");
      setComorbidities(Object.fromEntries(
        COMORBIDITIES.map((c) => [c, (rowComorb || {})[c] === "Yes" ? "Yes" : "No"])));
      setCohort(rest);
      setCohortResult(null);
      setActiveCohort(0);
      setCsvMsg(`Loaded ${list.length} patient${list.length === 1 ? "" : "s"} from “${file.name}” into the form + cohort below.`);
      window.scrollTo(0, 0);
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  };

  const updatePatient = (i, patch) =>
    setCohort((list) => list.map((p, j) => (j === i ? { ...p, ...patch } : p)));

  const downloadExcel = async () => {
    setCohortBusy("Preparing the Excel download...");
    try {
      const patients = [form, ...cohort].map((p, i) => ({
        ...p,
        // Patient 1's meds/symptoms/history live in the dedicated form states.
        ...(i === 0 ? { current_medications: meds,
                       symptoms: [...symptoms, ...(symptomOther.trim() ? [symptomOther.trim()] : [])] } : {}),
        patient_id: p.patient_id || `P${String(i + 1).padStart(3, "0")}`,
        comorbidities: Object.fromEntries(
          COMORBIDITIES.map((c) => [c, ((i === 0 ? comorbidities : p.comorbidities) || {})[c] || "No"])),
      }));
      const blob = await exportCohortExcel(patients);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `ctq_patients_${new Date().toISOString().slice(0, 10)}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setCohortBusy("");
    }
  };

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    if (cohort.length > 0) {
      // ---- cohort mode: one analysis per added patient ----
      const age = Number(form.age);
      if (!form.age || Number.isNaN(age) || age <= 0 || age > 120) {
        setError(`Patient 1 needs a valid age (1-120) before cohort matching can run.`);
        window.scrollTo(0, 0);
        return;
      }
      const patients = [form, ...cohort].map((p, i) => ({
        ...p,
        patient_id: p.patient_id || `P${String(i + 1).padStart(3, "0")}`,
      }));
      for (let i = 0; i < patients.length; i++) {
        const a = Number(patients[i].age);
        if (!patients[i].age || Number.isNaN(a) || a <= 0 || a > 120) {
          setError(`Patient ${i + 1} needs a valid age (1-120).`);
          window.scrollTo(0, 0);
          return;
        }
      }
      setCohortBusy(topK ? `Checking the top ${topK} best-matching trials for ${patients.length} patients...`
                          : `Checking every trial in the database for ${patients.length} patients...`);
      try {
        const built = patients.map((p, i) => {
          // Patient 1 is the main form: read meds/symptoms/history from the
          // dedicated states (the checkboxes/med rows the user sees + edits).
          // Patients 2+ carry their own CSV/form data.
          const isMain = i === 0;
          const fullComorbidities = Object.fromEntries(
            COMORBIDITIES.map((c) =>
              [c, ((isMain ? comorbidities : p.comorbidities) || {})[c] || "No"]));
          return buildPayload({
            ...p,
            comorbidities: fullComorbidities,
            current_medications: isMain ? meds : (p.current_medications || meds),
            symptoms: isMain
              ? [...symptoms, ...(symptomOther.trim() ? [symptomOther.trim()] : [])]
              : (p.symptoms || [...symptoms, ...(symptomOther.trim() ? [symptomOther.trim()] : [])]),
          });
        });
        const res = await analyzeCohort(built, topK);
        setCohortResult(res);
        setActiveCohort(0);
        window.scrollTo(0, 0);
      } catch (err) {
        setError(apiErrorMessage(err));
        window.scrollTo(0, 0);
      } finally {
        setCohortBusy("");
      }
      return;
    }
    // ---- single-patient mode (original path) ----
    const age = Number(form.age);
    if (!form.age || Number.isNaN(age) || age <= 0 || age > 120) {
      setError("Please enter a valid patient age (1-120).");
      window.scrollTo(0, 0);
      return;
    }
    setBusy(true);
    try {
      // Full form: unticked history items are explicitly recorded as "No"
      // (matching the hint shown in the UI).
      const fullComorbidities = Object.fromEntries(
        COMORBIDITIES.map((c) => [c, comorbidities[c] || "No"])
      );
      const payload = buildPayload({
        ...form,
        comorbidities: fullComorbidities,
        current_medications: meds,
        symptoms: [...symptoms, ...(symptomOther.trim() ? [symptomOther.trim()] : [])],
      });
      const response = await analyzePatient(payload, topK);
      sessionStorage.setItem("ctq_results", JSON.stringify({ response, profile: payload }));
      navigate("/results");
    } catch (err) {
      setError(apiErrorMessage(err));
      window.scrollTo(0, 0);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <h1>Patient → Trial Matcher</h1>
      <p style={{ color: "var(--muted)" }}>
        Enter patient information to find potentially relevant Indian clinical trials. All fields
        except age are optional - missing information leads to honest
        &quot;Insufficient Information&quot; verdicts rather than guesses.
      </p>

      <div className="card section-gap" style={{ padding: "0.9rem 1.1rem" }}>
        <div style={{ fontWeight: 600, fontSize: "0.88rem", marginBottom: "0.5rem" }}>
          Try it instantly with sample data
        </div>
        <div className="btn-row">
          {SAMPLE_PATIENTS.map((s) => (
            <button key={s.key} type="button" className="btn secondary"
              style={{ padding: "0.4rem 0.85rem", fontSize: "0.85rem" }}
              onClick={() => loadSample(s)}>
              {s.label}
            </button>
          ))}
        </div>
      </div>

      {/* -------- Cohort controls (structured multi-patient) -------- */}
      {tab === "structured" && (
        <div className="card section-gap" style={{ padding: "0.9rem 1.1rem" }}>
          <div className="result-head">
            <div>
              <div style={{ fontWeight: 700 }}>
                {cohort.length === 0
                  ? "Single patient mode"
                  : `${cohort.length + 1} patients in the cohort`}
              </div>
              <span className="hint">
                {cohort.length === 0
                  ? "Filling several patients? Add them below - each one gets its own trial check."
                  : "Patient 1 is the form above; the others are listed below it."}
              </span>
            </div>
            <div className="btn-row">
              <button type="button" className="btn secondary" onClick={addPatient}>
                + Add another patient
              </button>
              <button type="button" className="btn" onClick={downloadExcel} disabled={!!cohortBusy}>
                ⤓ Download all patients (Excel)
              </button>
              <button type="button" className="btn" onClick={() => csvFileRef.current?.click()} disabled={!!cohortBusy}>
                ⤒ Upload structured CSV
              </button>
              <input ref={csvFileRef} type="file" accept=".csv,.xlsx,.xls,.json" style={{ display: "none" }}
                onChange={(e) => { handleStructuredCsv(e.target.files?.[0]); e.target.value = ""; }} />
            </div>
          </div>
          {csvMsg && (
            <Banner kind="success" >{csvMsg}</Banner>
          )}
          {cohort.length > 0 && (
            <div className="btn-row section-gap" style={{ marginBottom: 0 }}>
              <button type="button" className="btn secondary"
                onClick={() => { setCohort([]); setCohortResult(null); }}>
                Clear cohort ({cohort.length + 1} patients)
              </button>
            </div>
          )}
        </div>
      )}

      <div className="btn-row" style={{ marginBottom: "0.9rem", flexWrap: "wrap" }}>
        <button type="button" className={`btn ${tab === "structured" ? "primary" : ""}`}
          onClick={() => setTab("structured")}>
          Structured Data (form)
        </button>
        <button type="button" className={`btn ${tab === "unstructured" ? "primary" : ""}`}
          onClick={() => setTab("unstructured")}>
          Unstructured Data (photos, PDF, CSV)
        </button>
      </div>

      {tab === "unstructured" && <UnstructuredPanel />}

      <form onSubmit={submit} style={{ display: tab === "structured" ? "" : "none" }}>
        {error && <Banner kind="error">{error}</Banner>}

        {cohort.map((p, i) => (
          <div key={i} className="card section-gap" style={{ padding: "1rem 1.2rem" }}>
            <div className="result-head">
              <div style={{ fontWeight: 700 }}>Patient {i + 2} of {cohort.length + 1}</div>
              <button type="button" className="btn secondary" style={{ padding: "0.3rem 0.8rem" }}
                onClick={() => removePatient(i)}>✕ Remove</button>
            </div>
            <div className="field-grid">
              <Field label="Patient ID">
                <input value={p.patient_id} onChange={(e) => updatePatient(i, { patient_id: e.target.value })} />
              </Field>
              <Field label="Age *">
                <input type="number" min="0" max="120" value={p.age}
                  onChange={(e) => updatePatient(i, { age: e.target.value })} />
              </Field>
              <Field label="Gender">
                <select value={p.gender} onChange={(e) => updatePatient(i, { gender: e.target.value })}>
                  <option value="">Select...</option><option>Female</option><option>Male</option><option>Other</option>
                </select>
              </Field>
              <Field label="Primary condition">
                <input value={p.condition} onChange={(e) => updatePatient(i, { condition: e.target.value })}
                  placeholder="e.g. Type 2 Diabetes" />
              </Field>
              <Field label="Disease duration (months)">
                <input type="number" min="0" value={p.disease_duration_months}
                  onChange={(e) => updatePatient(i, { disease_duration_months: e.target.value })} />
              </Field>
              <Field label="Height (cm)">
                <input type="number" step="0.1" value={p.height_cm}
                  onChange={(e) => updatePatient(i, { height_cm: e.target.value })} />
              </Field>
              <Field label="Weight (kg)">
                <input type="number" step="0.1" value={p.weight_kg}
                  onChange={(e) => updatePatient(i, { weight_kg: e.target.value })} />
              </Field>
              <Field label="HbA1c (%)">
                <input type="number" step="0.1" value={p.hba1c} onChange={(e) => updatePatient(i, { hba1c: e.target.value })} />
              </Field>
              <Field label="eGFR">
                <input type="number" value={p.egfr} onChange={(e) => updatePatient(i, { egfr: e.target.value })} />
              </Field>
              <Field label="FEV1 (% predicted)">
                <input type="number" value={p.fev1_percent} onChange={(e) => updatePatient(i, { fev1_percent: e.target.value })} />
              </Field>
              <Field label="Pregnancy status">
                <select value={p.pregnancy_status} onChange={(e) => updatePatient(i, { pregnancy_status: e.target.value })}>
                  <option value="">Select...</option><option>Not Pregnant</option><option>Pregnant</option><option>N-A</option>
                </select>
              </Field>
              <Field label="Smoking status">
                <select value={p.smoking_status} onChange={(e) => updatePatient(i, { smoking_status: e.target.value })}>
                  <option value="">Select...</option><option>Never</option><option>Former</option><option>Current</option>
                </select>
              </Field>
              <Field label="Alcohol use">
                <select value={p.alcohol_use} onChange={(e) => updatePatient(i, { alcohol_use: e.target.value })}>
                  <option value="">Select...</option><option>Never</option><option>Occasional</option><option>Regular</option>
                </select>
              </Field>
            </div>
            <div style={{ marginTop: "0.5rem" }}>
              <label style={{ fontWeight: 600, fontSize: "0.85rem" }}>Medical history</label>
              <div className="checkbox-grid">
                {COMORBIDITIES.map((c) => (
                  <label key={c} className="check-item">
                    <input type="checkbox" checked={(p.comorbidities || {})[c] === "Yes"}
                      onChange={(e) => updatePatient(i, {
                        comorbidities: { ...(p.comorbidities || {}), [c]: e.target.checked ? "Yes" : "No" },
                      })} />
                    {c}
                  </label>
                ))}
              </div>
            </div>
          </div>
        ))}

        <div className="card">
          <>
            {/* ---------------- Basic information ---------------- */}
            <h2>Basic Information</h2>
            <div className="field-grid">
              <Field label="Patient ID" hint="Any code, e.g. P001 - no personal names needed">
                <input value={form.patient_id} onChange={set("patient_id")} placeholder="P001" />
              </Field>
              <Field label="Age *"><input type="number" min="0" max="120" value={form.age} onChange={set("age")} /></Field>
              <Field label="Gender">
                <select value={form.gender} onChange={set("gender")}>
                  <option value="">Select...</option><option>Female</option><option>Male</option><option>Other</option>
                </select>
              </Field>
              <Field label="State"><input value={form.state} onChange={set("state")} placeholder="West Bengal" /></Field>
              <Field label="City"><input value={form.city} onChange={set("city")} placeholder="Kolkata" /></Field>
              <Field label="Height (cm)"><input type="number" step="0.1" value={form.height_cm} onChange={set("height_cm")} /></Field>
              <Field label="Weight (kg)"><input type="number" step="0.1" value={form.weight_kg} onChange={set("weight_kg")} /></Field>
            </div>

            {/* ---------------- Disease information ---------------- */}
            <h2 className="section-gap">Disease Information</h2>
            <div className="field-grid">
              <Field label="Primary disease / condition" hint="e.g. Type 2 Diabetes">
                <input value={form.condition} onChange={set("condition")} list="common-conditions" />
              </Field>
              <datalist id="common-conditions">
                {["Type 2 Diabetes", "Hypertension", "Asthma", "COPD", "Breast Cancer", "Rheumatoid Arthritis",
                  "Type 2 Diabetes with Diabetic Nephropathy", "Prediabetes", "Healthy Volunteer"].map((c) => <option key={c} value={c} />)}
              </datalist>
              <Field label="Disease duration (months)"><input type="number" min="0" value={form.disease_duration_months} onChange={set("disease_duration_months")} /></Field>
              <Field label="Disease severity">
                <select value={form.disease_severity} onChange={set("disease_severity")}>
                  <option value="">Select...</option><option>Mild</option><option>Moderate</option><option>Severe</option>
                </select>
              </Field>
              <Field label="Previous diagnosis"><input value={form.previous_diagnosis} onChange={set("previous_diagnosis")} /></Field>
            </div>

            <Field label="Symptoms" wide>
              <div className="checkbox-grid">
                {SYMPTOMS.map((s) => (
                  <label key={s} className="check-item">
                    <input type="checkbox" checked={symptoms.includes(s)}
                      onChange={(e) => setSymptoms((cur) => e.target.checked ? [...cur, s] : cur.filter((x) => x !== s))} />
                    {s}
                  </label>
                ))}
              </div>
            </Field>
            <Field label="Other symptoms"><input value={symptomOther} onChange={(e) => setSymptomOther(e.target.value)} placeholder="Comma separated" /></Field>

            {/* ---------------- Medical history ---------------- */}
            <h2 className="section-gap">Medical History</h2>
            <div className="checkbox-grid">
              {COMORBIDITIES.map((c) => (
                <label key={c} className="check-item">
                  <input type="checkbox" checked={comorbidities[c] === "Yes"}
                    onChange={(e) => setComorbidities((cur) => ({ ...cur, [c]: e.target.checked ? "Yes" : "No" }))} />
                  {c}
                </label>
              ))}
            </div>
            <p className="hint">Unticked items are recorded as &quot;No&quot;.</p>
            <Field label="Other medical history" wide>
              <textarea rows={2} value={form.other_medical_history} onChange={set("other_medical_history")}
                placeholder="Anything else clinically relevant" />
            </Field>

            {/* ---------------- Medications ---------------- */}
            <h2 className="section-gap">Medications</h2>
            {meds.map((m, i) => (
              <div key={i} className="med-row">
                <input style={{ flex: "2", minWidth: 160 }} placeholder="Medication name (e.g. Metformin)"
                  value={m.name} onChange={(e) => setMeds(meds.map((x, j) => j === i ? { ...x, name: e.target.value } : x))} />
                <input style={{ flex: "1", minWidth: 100 }} placeholder="Dose (e.g. 500 mg)"
                  value={m.dose || ""} onChange={(e) => setMeds(meds.map((x, j) => j === i ? { ...x, dose: e.target.value } : x))} />
                <input style={{ flex: "1", minWidth: 120 }} placeholder="Frequency (e.g. twice daily)"
                  value={m.frequency || ""} onChange={(e) => setMeds(meds.map((x, j) => j === i ? { ...x, frequency: e.target.value } : x))} />
                <input style={{ flex: "1", minWidth: 100 }} type="number" min="0" placeholder="Duration (months)"
                  value={m.duration_months || ""} onChange={(e) => setMeds(meds.map((x, j) => j === i ? { ...x, duration_months: e.target.value } : x))} />
                <button type="button" className="btn secondary" onClick={() => setMeds(meds.filter((_, j) => j !== i))}>Remove</button>
              </div>
            ))}
            <div className="btn-row" style={{ marginBottom: "1rem" }}>
              <button type="button" className="btn secondary" onClick={() => setMeds([...meds, { name: "", dose: "", frequency: "", duration_months: "" }])}>
                + Add medication
              </button>
            </div>
            <div className="field-grid">
              <Field label="Previous treatment failure?" hint="Did a prior therapy fail?">
                <MCQ value={form.treatment_failure} onChange={(v) => setForm((f) => ({ ...f, treatment_failure: v }))} />
              </Field>
              <Field label="Known drug allergies"><input value={form.drug_allergies} onChange={set("drug_allergies")} placeholder="e.g. Penicillin" /></Field>
            </div>

            {/* ---------------- Laboratory values ---------------- */}
            <h2 className="section-gap">Laboratory Values <span style={{ fontWeight: 400, fontSize: "0.85rem", color: "var(--muted)" }}>(all optional)</span></h2>
            <div className="field-grid">
              <Field label="HbA1c (%)" hint="e.g. 8.2"><input type="number" step="0.1" value={form.hba1c} onChange={set("hba1c")} /></Field>
              <Field label="Fasting glucose (mg/dL)"><input type="number" value={form.fasting_glucose} onChange={set("fasting_glucose")} /></Field>
              <Field label="Systolic BP (mmHg)"><input type="number" value={form.systolic_bp} onChange={set("systolic_bp")} /></Field>
              <Field label="Diastolic BP (mmHg)"><input type="number" value={form.diastolic_bp} onChange={set("diastolic_bp")} /></Field>
              <Field label="Creatinine (mg/dL)"><input type="number" step="0.01" value={form.creatinine} onChange={set("creatinine")} /></Field>
              <Field label="eGFR"><input type="number" value={form.egfr} onChange={set("egfr")} /></Field>
              <Field label="Hemoglobin (g/dL)"><input type="number" step="0.1" value={form.hemoglobin} onChange={set("hemoglobin")} /></Field>
              <Field label="WBC (cells/uL)"><input type="number" value={form.wbc} onChange={set("wbc")} /></Field>
              <Field label="Platelets (/uL)"><input type="number" value={form.platelets} onChange={set("platelets")} /></Field>
              <Field label="ALT (U/L)"><input type="number" value={form.alt} onChange={set("alt")} /></Field>
              <Field label="AST (U/L)"><input type="number" value={form.ast} onChange={set("ast")} /></Field>
              <Field label="Bilirubin (mg/dL)"><input type="number" step="0.01" value={form.bilirubin} onChange={set("bilirubin")} /></Field>
              <Field label="Cholesterol (mg/dL)"><input type="number" value={form.cholesterol} onChange={set("cholesterol")} /></Field>
              <Field label="FEV1 (% predicted)" hint="respiratory trials, e.g. 78"><input type="number" step="1" value={form.fev1_percent} onChange={set("fev1_percent")} /></Field>
            </div>
            <p className="hint">Trials needing other measurements are handled via the notes fields below.</p>

            {/* ---------------- Other eligibility information ---------------- */}
            <h2 className="section-gap">Other Eligibility Information</h2>
            <div className="field-grid">
              <Field label="Pregnancy status">
                <select value={form.pregnancy_status} onChange={set("pregnancy_status")}>
                  <option value="">Select...</option><option>Not Pregnant</option><option>Pregnant</option><option>N-A</option><option>Unknown</option>
                </select>
              </Field>
              <Field label="Smoking status">
                <select value={form.smoking_status} onChange={set("smoking_status")}>
                  <option value="">Select...</option><option>Never</option><option>Former</option><option>Current</option><option>Unknown</option>
                </select>
              </Field>
              <Field label="Alcohol use">
                <select value={form.alcohol_use} onChange={set("alcohol_use")}>
                  <option value="">Select...</option><option>Never</option><option>Occasional</option><option>Regular</option><option>Unknown</option>
                </select>
              </Field>
              <Field label="Previous clinical-trial participation">
                <MCQ value={form.prior_trial_participation} onChange={(v) => setForm((f) => ({ ...f, prior_trial_participation: v }))} />
              </Field>
              <Field label="Surgery history"><input value={form.surgery_history} onChange={set("surgery_history")} placeholder="e.g. Appendectomy 2019" /></Field>
              <Field label="Infection history"><input value={form.infection_history} onChange={set("infection_history")} placeholder="e.g. TB in 2015" /></Field>
              <Field label="Organ function notes" wide hint="Anything relevant beyond the lab values above">
                <input value={form.organ_function_notes} onChange={set("organ_function_notes")} />
              </Field>
            </div>
          </>

          <div className="btn-row section-gap" style={{ flexWrap: "wrap", alignItems: "center" }}>
            <TrialScopePicker value={trialScope} onChange={setTrialScope} />
          </div>
          <div className="btn-row section-gap">
            <button type="submit" className="btn large" disabled={busy || !!cohortBusy}>
              {busy ? "Analyzing..."
                : cohortBusy ? "Analyzing cohort..."
                : cohort.length > 0 ? `Find Trials for all ${cohort.length + 1} patients`
                : "Find Matching Trials"}
            </button>
            {busy && <span style={{ color: "var(--muted)" }}>Retrieving, scoring similarity and checking eligibility criteria...</span>}
            {cohortBusy && <span style={{ color: "var(--muted)" }}>{cohortBusy}</span>}
          </div>
        </div>
      </form>

      {cohortResult && (
        <div className="section-gap">
          <h2>Cohort Results</h2>
          {(() => {
            const ok = cohortResult.results.filter((r) => r.ok);
            const failed = cohortResult.results.filter((r) => !r.ok);
            const active = ok[activeCohort];
            if (!active) return <Banner kind="warn">No patient results available.</Banner>;
            const trials = active.response?.results || [];
            return (
              <>
                <Banner kind={failed.length === 0 ? "success" : "warn"}>
                  {ok.length} of {cohortResult.results.length} patients analysed
                  {failed.length > 0 && <> · failed: {failed.map((f) => f.patient_id).join(", ")}</>}
                </Banner>
                <div className="card section-gap">
                  <div className="btn-row" style={{ flexWrap: "wrap", marginBottom: "0.6rem" }}>
                    {ok.map((r, i) => (
                      <button key={r.patient_id} type="button"
                        className={`btn ${i === activeCohort ? "primary" : ""}`}
                        style={{ padding: "0.35rem 0.9rem" }}
                        onClick={() => setActiveCohort(i)}>
                        {r.patient_id}
                      </button>
                    ))}
                  </div>
                  <div className="btn-row" style={{ marginBottom: "0.6rem" }}>
                    <button type="button" className="btn secondary" disabled={activeCohort === 0}
                      onClick={() => setActiveCohort((i) => Math.max(0, i - 1))}>
                      ← Previous patient
                    </button>
                    <span style={{ fontWeight: 600 }}>Patient {activeCohort + 1} of {ok.length}</span>
                    <button type="button" className="btn secondary"
                      disabled={activeCohort >= ok.length - 1}
                      onClick={() => setActiveCohort((i) => Math.min(ok.length - 1, i + 1))}>
                      Next patient →
                    </button>
                    <button type="button" className="btn"
                      onClick={() => {
                        sessionStorage.setItem("ctq_results", JSON.stringify(
                          { response: active.response, profile: {} }));
                        navigate("/results");
                      }}>
                      Open full page view for {active.patient_id}
                    </button>
                  </div>
                  <h3>Trials for {active.patient_id} — {trials.length} checked</h3>
                  {trials.map((t) => (
                    <div key={t.trial_id}
                      className={`result-card section-gap ${t.eligibility === "Potentially Eligible" ? "eligible" : t.eligibility === "Not Eligible" ? "not-eligible" : "insufficient"}`}
                      style={{ padding: "0.8rem 1rem" }}>
                      <div className="result-head">
                        <div>
                          <div className="trial-id">{t.trial_id}</div>
                          <div className="result-title">{t.title}</div>
                        </div>
                      </div>
                      <div className="result-meta">
                        <EligibilityBadge status={t.eligibility} />
                        <MatchScore percent={t.match_percent ?? Math.round((t.similarity_score || 0) * 100)}
                          similarity={t.similarity_score} />
                        <MetaChip>{t.condition}</MetaChip>
                        <MetaChip>{t.status}</MetaChip>
                      </div>
                      {t.reasons_for?.length > 0 && (
                        <ul className="hint" style={{ margin: "0.4rem 0 0" }}>
                          {t.reasons_for.slice(0, 3).map((x, i) => <li key={i}>{x}</li>)}
                        </ul>
                      )}
                    </div>
                  ))}
                </div>
              </>
            );
          })()}
        </div>
      )}
    </div>
  );
}
