import axios from "axios";

/** Central API client for the CTQ backend. */
// Dev server proxies nothing, so it must target 127.0.0.1:8000 directly;
// production builds are served BY the backend, so a relative /api works
// (keeps a hosted/share link on one origin, no CORS needed).
const api = axios.create({
  baseURL:
    import.meta.env.VITE_API_URL ||
    (import.meta.env.DEV ? "http://127.0.0.1:8000/api" : "/api"),
  timeout: 120000,
});

/** Extract a friendly error message from an axios/FastAPI error. */
export function apiErrorMessage(error) {
  if (error?.response?.data?.detail) {
    const d = error.response.data.detail;
    return typeof d === "string" ? d : JSON.stringify(d);
  }
  if (error?.code === "ECONNREFUSED") {
    return "Cannot reach the CTQ backend. Is it running on port 8000? (see README: uvicorn main:app --port 8000)";
  }
  return error?.message || "Unexpected error. Please try again.";
}

/** Normalise a medication entry to {name, dose, frequency, duration_months}. */
function normaliseMeds(meds) {
  if (!meds) return [];
  return meds
    .map((m) => (typeof m === "string" ? { name: m } : m))
    .filter((m) => m && m.name && m.name.trim())
    .map((m) => ({
      name: m.name.trim(),
      dose: (m.dose || "").trim() || null,
      frequency: (m.frequency || "").trim() || null,
      duration_months: m.duration_months ? Number(m.duration_months) : null,
    }));
}

/**
 * Build the structured profile payload consumed by /patient/analyze.
 * Accepts the full-form state; quick-mode state maps into the same shape.
 */
export function buildPayload(form) {
  const payload = {
    patient_id: form.patient_id || "",
    age: form.age || null,
    gender: form.gender || null,
    state: form.state || null,
    city: form.city || null,
    height_cm: form.height_cm || null,
    weight_kg: form.weight_kg || null,
    condition: form.condition || null,
    disease_duration_months: form.disease_duration_months || null,
    disease_severity: form.disease_severity || null,
    symptoms: form.symptoms || [],
    previous_diagnosis: form.previous_diagnosis || null,
    previous_treatments: form.previous_treatments || [],
    comorbidities: form.comorbidities || {},
    other_medical_history: form.other_medical_history || null,
    current_medications: normaliseMeds(form.current_medications),
    previous_medications: form.previous_medications || [],
    treatment_failure: form.treatment_failure || "Unknown",
    drug_allergies: form.drug_allergies || null,
    hba1c: form.hba1c || null,
    fasting_glucose: form.fasting_glucose || null,
    systolic_bp: form.systolic_bp || null,
    diastolic_bp: form.diastolic_bp || null,
    creatinine: form.creatinine || null,
    egfr: form.egfr || null,
    hemoglobin: form.hemoglobin || null,
    wbc: form.wbc || null,
    platelets: form.platelets || null,
    alt: form.alt || null,
    ast: form.ast || null,
    bilirubin: form.bilirubin || null,
    cholesterol: form.cholesterol || null,
    fev1_percent: form.fev1_percent || null,
    pregnancy_status: form.pregnancy_status || null,
    smoking_status: form.smoking_status || null,
    alcohol_use: form.alcohol_use || null,
    prior_trial_participation: form.prior_trial_participation || "Unknown",
    surgery_history: form.surgery_history || null,
    infection_history: form.infection_history || null,
    organ_function_notes: form.organ_function_notes || null,
  };
  if (form.quick_answers) payload.quick_answers = form.quick_answers;
  return payload;
}

// ---------------------------------------------------------------------------
// Endpoints
// ---------------------------------------------------------------------------

export const analyzePatient = (payload, topK = null) =>
  api.post("/patient/analyze", payload, { params: topK ? { top_k: topK } : {} })
    .then((r) => r.data);

export const getTrials = (params = {}) => api.get("/trials", { params }).then((r) => r.data);

export const getTrial = (trialId) =>
  api.get(`/trials/${encodeURIComponent(trialId)}`).then((r) => r.data);

// ---------------------------------------------------------------------------
// Live trial ingestion (ClinicalTrials.gov)
// ---------------------------------------------------------------------------

export const getLivePresets = () =>
  api.get("/trials/live/presets").then((r) => r.data);

export const importLiveTrials = (condition, maxStudies = 15, indiaOnly = true, recruitingOnly = true) =>
  api.post("/trials/import/live",
           { condition, max_studies: maxStudies, india_only: indiaOnly, recruiting_only: recruitingOnly },
           { timeout: 180000 }).then((r) => r.data);

export const getMeta = () => api.get("/meta").then((r) => r.data);

export const getHealth = () => api.get("/health").then((r) => r.data);

export const uploadPatients = (file) => {
  const fd = new FormData();
  fd.append("file", file);
  return api.post("/upload/patients", fd).then((r) => r.data);
};

export const uploadLabels = (file) => {
  const fd = new FormData();
  fd.append("file", file);
  return api.post("/upload/labels", fd).then((r) => r.data);
};

export const runEvaluation = (patients, labels, topK = null) =>
  api.post("/patient/analyze-batch", { patients, labels },
           { timeout: 600000, ...(topK ? { params: { top_k: topK } } : {}) }).then((r) => r.data);

export const runSampleEvaluation = () =>
  api.post("/evaluation/run-sample").then((r) => r.data);

export const getEvaluationRuns = () =>
  api.get("/evaluation/runs").then((r) => r.data);

// ---------------------------------------------------------------------------
// Unstructured data -> ML extraction (DistilBERT NER)
// ---------------------------------------------------------------------------

export const extractDocument = (file) => {
  const fd = new FormData();
  fd.append("file", file);
  return api.post("/extract/document", fd, { timeout: 600000 }).then((r) => r.data);
};

export const getNERStatus = () => api.get("/ner/status").then((r) => r.data);

/** Bundled synthetic sample data: notes + ground-truth labels (one click). */
export const getEvaluationSample = () =>
  api.get("/evaluation/sample-data").then((r) => r.data);

/** Calibrate similarity thresholds on the bundled labelled dataset. */
export const calibrateThresholds = () =>
  api.post("/evaluation/calibrate-thresholds", null, { timeout: 300000 }).then((r) => r.data);

/** Persisted threshold calibration (null when never calibrated). */
export const getThresholds = () =>
  api.get("/evaluation/thresholds").then((r) => r.data);

export const analyzeBatch = (patients, labels) =>
  api.post("/patient/analyze-batch", { patients, labels }, { timeout: 600000 }).then((r) => r.data);

// ---------------------------------------------------------------------------
// Cohort mode (multiple patients in one go)
// ---------------------------------------------------------------------------

export const analyzeCohort = (patients, topK = null) =>
  api.post("/cohort/analyze", { patients },
           { timeout: 600000, ...(topK ? { params: { top_k: topK } } : {}) }).then((r) => r.data);

export const exportCohortExcel = (patients) =>
  api.post("/cohort/export", { patients }, { responseType: "blob" }).then((r) => r.data);

/** Excel download of cohort matching RESULTS (one row per patient-trial). */
export const exportResultsExcel = (patients, results, lang = "en") =>
  api.post("/cohort/export-results", { patients, results, lang },
           { responseType: "blob", timeout: 120000 }).then((r) => r.data);

export default api;
