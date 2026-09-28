"""Generate the sample datasets used for demos and model evaluation.

Outputs (backend/data/):
  trials.json             - synthetic CTRI-style Indian clinical trials
  sample_patients.csv     - 80 synthetic Indian patients (unlabelled)
  sample_ground_truth.csv - patient x trial labels (1/0/2)

The generator deliberately creates:
  clearly eligible, clearly ineligible, borderline, missing-information and
  exclusion-criterion cases, so the evaluation section is meaningful.

All data is synthetic - no real patient information is used.

Run:  python generate_data.py
"""
import csv
import json
import random
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(exist_ok=True)

random.seed(42)

STATES = [
    ("West Bengal", ["Kolkata", "Howrah", "Siliguri"]),
    ("Maharashtra", ["Mumbai", "Pune", "Nagpur"]),
    ("Tamil Nadu", ["Chennai", "Coimbatore", "Madurai"]),
    ("Karnataka", ["Bengaluru", "Mysuru", "Hubballi"]),
    ("Delhi", ["New Delhi"]),
    ("Telangana", ["Hyderabad", "Warangal"]),
    ("Gujarat", ["Ahmedabad", "Surat", "Vadodara"]),
    ("Uttar Pradesh", ["Lucknow", "Kanpur", "Varanasi"]),
    ("Kerala", ["Thiruvananthapuram", "Kochi", "Kozhikode"]),
    ("Punjab", ["Ludhiana", "Amritsar", "Patiala"]),
    ("Rajasthan", ["Jaipur", "Jodhpur", "Udaipur"]),
    ("Odisha", ["Bhubaneswar", "Cuttack"]),
]

FIRST_M = ["Aarav", "Vivaan", "Rohan", "Kabir", "Arjun", "Aditya", "Rahul", "Sanjay", "Vikram", "Imran", "Joseph", "Devanand", "Manoj", "Rajesh", "Suresh", "Amit", "Pranav", "Naveen", "Farhan", "Gurpreet"]
FIRST_F = ["Ananya", "Diya", "Priya", "Meera", "Kavya", "Anjali", "Sneha", "Pooja", "Lakshmi", "Fatima", "Aisha", "Ritu", "Sunita", "Nandini", "Shreya", "Divya", "Rekha", "Gayatri", "Nisha", "Harleen"]
SURNAMES = ["Sharma", "Patel", "Reddy", "Iyer", "Banerjee", "Das", "Gupta", "Nair", "Mehta", "Khan", "Chatterjee", "Rao", "Joshi", "Pillai", "Singh", "Verma", "Mukherjee", "Desai", "Kulkarni", "Bose"]

SPONSORS = [
    "AIIMS New Delhi", "PGIMER Chandigarh", "Apollo Hospitals", "Fortis Healthcare",
    "Nizam's Institute of Medical Sciences", "Christian Medical College Vellore",
    "Sun Pharma", "Cipla Ltd", "Biocon", "Zydus Cadila", "Lupin Ltd",
    "Tata Memorial Centre", "Sri Ramachandra Institute", "KEM Hospital Mumbai",
]


def random_location() -> str:
    state, cities = random.choice(STATES)
    return f"{random.choice(cities)}, {state}"


def random_locations(n: int = None) -> list:
    n = n or random.choice([1, 2, 3, 4])
    out = []
    while len(out) < n:
        loc = random_location()
        if loc not in out:
            out.append(loc)
    return out


# ---------------------------------------------------------------------------
# 1. Synthetic Indian trials (CTRI-style records)
# ---------------------------------------------------------------------------
TRIALS = [
    {
        "trial_id": "CTRI/2024/01/062001",
        "title": "A Randomised Open Label Trial of Glimepiride Add-on to Metformin in Type 2 Diabetes Mellitus",
        "condition": "Type 2 Diabetes Mellitus",
        "status": "Recruiting", "phase": "Phase III", "study_type": "Interventional",
        "gender": "Both", "min_age": 30, "max_age": 65,
        "inclusion_criteria": [
            "Adults aged 30-65 years diagnosed with Type 2 Diabetes Mellitus",
            "HbA1c between 7.5 and 10.5 percent at screening",
            "On stable metformin therapy for at least 3 months",
            "Body mass index between 23 and 35",
        ],
        "exclusion_criteria": [
            "Type 1 diabetes or history of diabetic ketoacidosis",
            "eGFR below 45",
            "Pregnant or breastfeeding women",
            "Severe hepatic impairment with ALT above 3 times upper limit of normal",
        ],
        "interventions": ["Glimepiride", "Metformin"], "sponsor": "Sun Pharma",
    },
    {
        "trial_id": "CTRI/2024/02/062115",
        "title": "Observational Study of Glycaemic Variability in Newly Diagnosed Type 2 Diabetes Patients in Urban India",
        "condition": "Type 2 Diabetes",
        "status": "Recruiting", "phase": "N/A", "study_type": "Observational",
        "gender": "Both", "min_age": 25, "max_age": 60,
        "inclusion_criteria": [
            "Newly diagnosed Type 2 Diabetes within the past 6 months",
            "Age 25-60 years",
            "HbA1c between 6.5 and 9 percent",
            "No previous treatment with insulin",
        ],
        "exclusion_criteria": [
            "Chronic kidney disease with eGFR below 60",
            "Current use of insulin",
            "Pregnancy",
        ],
        "interventions": ["Continuous glucose monitoring"], "sponsor": "AIIMS New Delhi",
    },
    {
        "trial_id": "CTRI/2024/03/062318",
        "title": "Evaluation of a Fixed Dose Combination of Perindopril and Indapamide in Uncontrolled Hypertension",
        "condition": "Hypertension",
        "status": "Recruiting", "phase": "Phase III", "study_type": "Interventional",
        "gender": "Both", "min_age": 40, "max_age": 75,
        "inclusion_criteria": [
            "Adults 40-75 years with uncontrolled hypertension",
            "Systolic BP between 140 and 180 despite monotherapy",
            "Diagnosis of hypertension for at least 6 months",
        ],
        "exclusion_criteria": [
            "Secondary hypertension",
            "Severe renal impairment with eGFR below 30",
            "History of stroke within past 6 months",
            "Pregnant or lactating women",
        ],
        "interventions": ["Perindopril", "Indapamide"], "sponsor": "Zydus Cadila",
    },
    {
        "trial_id": "CTRI/2024/04/062402",
        "title": "Phase II Study of a Novel HER2 Targeted Therapy in Metastatic Breast Cancer",
        "condition": "Breast Cancer",
        "status": "Recruiting", "phase": "Phase II", "study_type": "Interventional",
        "gender": "Female", "min_age": 18, "max_age": 70,
        "inclusion_criteria": [
            "Histologically confirmed HER2 positive metastatic breast cancer",
            "Female patients aged 18-70",
            "ECOG performance status 0-2",
            "Adequate organ function: hemoglobin above 9, platelets above 100000, ALT below 2.5 times ULN",
        ],
        "exclusion_criteria": [
            "Prior treatment with the same HER2 targeted agent",
            "Active infection requiring systemic therapy",
            "Pregnancy or breastfeeding",
        ],
        "interventions": ["HER2 targeted monoclonal antibody"], "sponsor": "Biocon",
    },
    {
        "trial_id": "CTRI/2024/05/062517",
        "title": "Bioequivalence Study of a Generic Atorvastatin 10 mg Tablet in Healthy Indian Volunteers",
        "condition": "Healthy Volunteers",
        "status": "Recruiting", "phase": "Phase I", "study_type": "Interventional",
        "gender": "Both", "min_age": 18, "max_age": 45,
        "inclusion_criteria": [
            "Healthy adults aged 18-45",
            "Body mass index between 18.5 and 25",
            "Normal laboratory parameters within reference range",
        ],
        "exclusion_criteria": [
            "Any chronic disease including diabetes, hypertension, liver or kidney disease",
            "Smoking or regular alcohol use",
            "Participation in another clinical trial within past 90 days",
        ],
        "interventions": ["Atorvastatin 10 mg"], "sponsor": "Cipla Ltd",
    },
    {
        "trial_id": "CTRI/2024/06/062633",
        "title": "Effects of Yoga Add-on Therapy on Glycaemic Control in Type 2 Diabetes Patients",
        "condition": "Type 2 Diabetes",
        "status": "Recruiting", "phase": "N/A", "study_type": "Interventional",
        "gender": "Both", "min_age": 35, "max_age": 70,
        "inclusion_criteria": [
            "Type 2 Diabetes diagnosed at least 1 year ago",
            "Age 35-70 years",
            "HbA1c between 7 and 10 percent",
            "Willing to attend supervised yoga sessions 3 times per week",
        ],
        "exclusion_criteria": [
            "Proliferative diabetic retinopathy",
            "Severe musculoskeletal disorders preventing exercise",
            "Uncontrolled hypertension with systolic BP above 180",
            "eGFR below 30",
        ],
        "interventions": ["Structured yoga program"], "sponsor": "S-VYASA Bengaluru",
    },
    {
        "trial_id": "CTRI/2024/07/062744",
        "title": "Study of Empagliflozin in Type 2 Diabetes Patients with Diabetic Nephropathy",
        "condition": "Type 2 Diabetes with Diabetic Nephropathy",
        "status": "Recruiting", "phase": "Phase III", "study_type": "Interventional",
        "gender": "Both", "min_age": 30, "max_age": 75,
        "inclusion_criteria": [
            "Type 2 Diabetes with established diabetic nephropathy",
            "eGFR between 30 and 75",
            "Age 30-75 years",
            "Urinary albumin to creatinine ratio above 300",
        ],
        "exclusion_criteria": [
            "Polycystic kidney disease",
            "Immunosuppressive therapy within past 6 months",
            "Type 1 diabetes",
        ],
        "interventions": ["Empagliflozin"], "sponsor": "Boehringer Ingelheim India",
    },
    {
        "trial_id": "CTRI/2024/08/062851",
        "title": "Comparison of Inhaled Budesonide-Formoterol versus Salbutamol in Mild to Moderate Asthma",
        "condition": "Asthma",
        "status": "Recruiting", "phase": "Phase IV", "study_type": "Interventional",
        "gender": "Both", "min_age": 12, "max_age": 60,
        "inclusion_criteria": [
            "Physician diagnosed mild to moderate persistent asthma",
            "Age 12-60 years",
            "FEV1 between 60 and 90 percent of predicted at screening",
            "Non-smoker for at least 1 year",
        ],
        "exclusion_criteria": [
            "Current smoking",
            "History of life-threatening asthma exacerbation",
            "Chronic obstructive pulmonary disease",
        ],
        "interventions": ["Budesonide-Formoterol inhaler"], "sponsor": "Cipla Ltd",
    },
    {
        "trial_id": "CTRI/2024/09/062966",
        "title": "Adalimumab Biosimilar in Moderate to Severe Rheumatoid Arthritis Inadequately Controlled by Methotrexate",
        "condition": "Rheumatoid Arthritis",
        "status": "Recruiting", "phase": "Phase III", "study_type": "Interventional",
        "gender": "Both", "min_age": 18, "max_age": 65,
        "inclusion_criteria": [
            "Rheumatoid arthritis as per ACR/EULAR criteria for at least 6 months",
            "Age 18-65",
            "Active disease despite methotrexate therapy for 3 months",
        ],
        "exclusion_criteria": [
            "Active tuberculosis or other serious infection",
            "Severe hepatic impairment",
            "Pregnancy or breastfeeding",
            "Prior treatment with any biologic DMARD",
        ],
        "interventions": ["Adalimumab biosimilar"], "sponsor": "Lupin Ltd",
    },
    {
        "trial_id": "CTRI/2024/10/063019",
        "title": "Prevalence of Anaemia Among Pregnant Women Attending Antenatal Clinics in Rural India",
        "condition": "Anaemia in Pregnancy",
        "status": "Recruiting", "phase": "N/A", "study_type": "Observational",
        "gender": "Female", "min_age": 18, "max_age": 40,
        "inclusion_criteria": [
            "Pregnant women aged 18-40 in second or third trimester",
            "Willing to provide blood sample for hemoglobin estimation",
        ],
        "exclusion_criteria": [
            "Known hemoglobinopathy",
            "Malignancy",
        ],
        "interventions": [], "sponsor": "PGIMER Chandigarh",
    },
    {
        "trial_id": "CTRI/2024/11/063128",
        "title": "Vitamin D Supplementation in Prediabetic Adults: A Randomised Controlled Trial",
        "condition": "Prediabetes",
        "status": "Recruiting", "phase": "Phase II", "study_type": "Interventional",
        "gender": "Both", "min_age": 30, "max_age": 60,
        "inclusion_criteria": [
            "Prediabetes confirmed by impaired fasting glucose 110-125 or HbA1c 5.7-6.4 percent",
            "Age 30-60 years",
            "Serum vitamin D level below 30 ng/mL",
        ],
        "exclusion_criteria": [
            "Diabetes mellitus on treatment",
            "Chronic kidney disease stage 3 or higher",
            "History of kidney stones",
        ],
        "interventions": ["Vitamin D3 60000 IU weekly"], "sponsor": "AIIMS New Delhi",
    },
    {
        "trial_id": "CTRI/2024/12/063237",
        "title": "Effect of SGLT2 Inhibitor on Cardiac Parameters in Type 2 Diabetes with Heart Failure",
        "condition": "Type 2 Diabetes with Heart Failure",
        "status": "Not Recruiting", "phase": "Phase III", "study_type": "Interventional",
        "gender": "Both", "min_age": 40, "max_age": 80,
        "inclusion_criteria": [
            "Type 2 Diabetes with chronic heart failure NYHA class II-III",
            "Left ventricular ejection fraction 40 percent or below",
            "Age 40-80 years",
        ],
        "exclusion_criteria": [
            "Acute decompensated heart failure within past month",
            "eGFR below 25",
            "Type 1 diabetes",
        ],
        "interventions": ["Dapagliflozin"], "sponsor": "Apollo Hospitals",
    },
    {
        "trial_id": "CTRI/2025/01/063344",
        "title": "Cognitive Behavioural Therapy for Depressive Symptoms in Type 2 Diabetes Patients",
        "condition": "Type 2 Diabetes with Depression",
        "status": "Recruiting", "phase": "N/A", "study_type": "Interventional",
        "gender": "Both", "min_age": 25, "max_age": 65,
        "inclusion_criteria": [
            "Type 2 Diabetes for at least 1 year",
            "PHQ-9 score between 10 and 20 indicating moderate depression",
            "Age 25-65 years",
        ],
        "exclusion_criteria": [
            "Current suicidal ideation",
            "Bipolar disorder or psychosis",
            "Substance dependence",
        ],
        "interventions": ["Cognitive behavioural therapy"], "sponsor": "NIMHANS Bengaluru",
    },
    {
        "trial_id": "CTRI/2025/02/063459",
        "title": "Long Term Safety Registry of a Biosimilar Rituximab in Indian Patients",
        "condition": "Rituximab Treated Conditions",
        "status": "Recruiting", "phase": "Phase IV", "study_type": "Observational",
        "gender": "Both", "min_age": 18, "max_age": 80,
        "inclusion_criteria": [
            "Patients prescribed biosimilar rituximab as part of routine care",
            "Age 18-80 years",
        ],
        "exclusion_criteria": [
            "Inability to attend follow-up visits",
        ],
        "interventions": [], "sponsor": "Zydus Cadila",
    },
    {
        "trial_id": "CTRI/2025/03/063561",
        "title": "Screening and Lifestyle Intervention for Non Alcoholic Fatty Liver Disease in Urban Workplaces",
        "condition": "Non Alcoholic Fatty Liver Disease",
        "status": "Recruiting", "phase": "N/A", "study_type": "Interventional",
        "gender": "Both", "min_age": 25, "max_age": 55,
        "inclusion_criteria": [
            "Ultrasound confirmed fatty liver",
            "Age 25-55 years",
            "Body mass index above 25",
            "No significant alcohol consumption",
        ],
        "exclusion_criteria": [
            "Viral hepatitis B or C",
            "Cirrhosis",
            "Regular alcohol use",
        ],
        "interventions": ["Diet and lifestyle coaching"], "sponsor": "KEM Hospital Mumbai",
    },
    {
        "trial_id": "CTRI/2025/04/063673",
        "title": "A Study to Assess the Efficacy of a Novel Fixed Dose Triple Combination in Moderate to Severe COPD",
        "condition": "Chronic Obstructive Pulmonary Disease",
        "status": "Recruiting", "phase": "Phase III", "study_type": "Interventional",
        "gender": "Both", "min_age": 40, "max_age": 80,
        "inclusion_criteria": [
            "Moderate to severe COPD with post-bronchodilator FEV1/FVC below 0.70",
            "Age 40-80 years",
            "Current or former smoker with at least 10 pack years",
            "History of at least one exacerbation in past year",
        ],
        "exclusion_criteria": [
            "Asthma as primary diagnosis",
            "Oxygen therapy dependence",
            "Recent myocardial infarction within 6 months",
        ],
        "interventions": ["Triple combination inhaler"], "sponsor": "Lupin Ltd",
    },
    {
        "trial_id": "CTRI/2025/05/063788",
        "title": "Effectiveness of Insulin Degludec versus Glargine in Insulin Naive Type 2 Diabetes Patients",
        "condition": "Type 2 Diabetes",
        "status": "Recruiting", "phase": "Phase III", "study_type": "Interventional",
        "gender": "Both", "min_age": 18, "max_age": 70,
        "inclusion_criteria": [
            "Type 2 Diabetes inadequately controlled on oral agents",
            "HbA1c between 7.5 and 11 percent",
            "Age 18-70 years",
            "Insulin naive - no previous insulin treatment",
        ],
        "exclusion_criteria": [
            "History of severe hypoglycaemia in past 6 months",
            "eGFR below 30",
            "Pregnancy or planned pregnancy",
            "Active malignancy",
        ],
        "interventions": ["Insulin degludec", "Insulin glargine"], "sponsor": "Novo Nordisk India",
    },
    {
        "trial_id": "CTRI/2025/06/063892",
        "title": "Telemedicine Follow-up versus In-person Visits in Post Myocardial Infarction Patients",
        "condition": "Post Myocardial Infarction",
        "status": "Recruiting", "phase": "N/A", "study_type": "Observational",
        "gender": "Both", "min_age": 30, "max_age": 75,
        "inclusion_criteria": [
            "Myocardial infarction within past 3 to 12 months",
            "Age 30-75 years",
            "Access to a smartphone",
        ],
        "exclusion_criteria": [
            "Ongoing unstable angina",
            "Severe cognitive impairment",
        ],
        "interventions": [], "sponsor": "Christian Medical College Vellore",
    },
    {
        "trial_id": "CTRI/2025/07/063911",
        "title": "Vaccination Response Study in Adults with Type 2 Diabetes",
        "condition": "Type 2 Diabetes",
        "status": "Recruiting", "phase": "N/A", "study_type": "Observational",
        "gender": "Both", "min_age": 40, "max_age": 70,
        "inclusion_criteria": [
            "Type 2 Diabetes diagnosed at least 2 years ago",
            "Age 40-70 years",
            "HbA1c between 6.5 and 10 percent",
            "No prior dose of the study vaccine",
        ],
        "exclusion_criteria": [
            "Immunosuppressive therapy",
            "Acute febrile illness at enrolment",
            "History of severe allergic reaction to vaccines",
        ],
        "interventions": [], "sponsor": "PGIMER Chandigarh",
    },
    {
        "trial_id": "CTRI/2025/08/064022",
        "title": "Ertugliflozin versus Placebo Add-on to Metformin in Type 2 Diabetes with Obesity",
        "condition": "Type 2 Diabetes with Obesity",
        "status": "Recruiting", "phase": "Phase III", "study_type": "Interventional",
        "gender": "Both", "min_age": 18, "max_age": 68,
        "inclusion_criteria": [
            "Type 2 Diabetes on stable metformin for 8 weeks or more",
            "Body mass index between 30 and 45",
            "HbA1c between 7.5 and 10.5 percent",
            "Age 18-68 years",
        ],
        "exclusion_criteria": [
            "eGFR below 45",
            "Recurrent genital mycotic infections",
            "Type 1 diabetes",
            "Pregnant or breastfeeding women",
        ],
        "interventions": ["Ertugliflozin"], "sponsor": "Pfizer India",
    },
]


def write_trials() -> None:
    now = "2025-08-15"
    for t in TRIALS:
        t["locations"] = random_locations()
        t["source"] = "CTRI (synthetic demo dataset)"
        t["last_updated"] = now
    (DATA_DIR / "trials.json").write_text(
        json.dumps(TRIALS, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"[data] wrote {len(TRIALS)} trials to data/trials.json")


# ---------------------------------------------------------------------------
# 2. Synthetic Indian patients
# ---------------------------------------------------------------------------

def make_patient(idx: int) -> dict:
    pid = f"P{idx:03d}"
    gender = random.choice(["Male", "Female", "Female", "Male"])
    first = random.choice(FIRST_M if gender == "Male" else FIRST_F)
    state, cities = random.choice(STATES)
    city = random.choice(cities)
    height = round(random.uniform(1.50, 1.82), 2)
    weight = round(random.uniform(48, 104), 1)
    bmi = round(weight / height ** 2, 1)
    p = {
        "patient_id": pid, "name": f"{first} {random.choice(SURNAMES)}",  # synthetic only
        "gender": gender, "city": city, "state": state,
        "height_cm": round(height * 100), "weight_kg": weight, "bmi": bmi,
    }
    archetype = idx % 8  # 8 structured archetypes -> balanced evaluation cases

    if archetype in (0, 1, 2, 4):  # diabetes-centric patients
        p["condition"] = "Type 2 Diabetes"
        p["disease_duration_months"] = random.choice([4, 10, 24, 36, 60, 120])
        p["disease_severity"] = random.choice(["Mild", "Moderate", "Moderate", "Severe"])
        p["age"] = random.choice([29, 34, 41, 47, 47, 52, 58, 63, 66, 71, 72])
        p["hba1c"] = round(random.uniform(5.8, 11.2), 1)
        p["fasting_glucose"] = round(random.uniform(100, 240))
        p["systolic_bp"] = round(random.uniform(118, 172))
        p["diastolic_bp"] = round(random.uniform(74, 102))
        p["previous_diagnosis"] = "Type 2 Diabetes Mellitus"
        on_metformin = random.random() < 0.8
        meds = []
        if on_metformin:
            meds.append({"name": "Metformin", "duration_months": random.choice([6, 12, 24])})
        if random.random() < 0.4:
            meds.append({"name": "Glimepiride", "duration_months": random.choice([3, 6, 12])})
        if random.random() < 0.35:
            meds.append({"name": "Telmisartan", "duration_months": random.choice([6, 12])})
        p["current_medications"] = meds
        p["comorbidities"] = {"Diabetes": "Yes"}
        if random.random() < 0.45:
            p["comorbidities"]["Hypertension"] = "Yes"
        if random.random() < 0.15:
            p["comorbidities"]["Kidney disease"] = "Yes"
            p["egfr"] = round(random.uniform(22, 55), 1)
        elif random.random() < 0.4:
            p["egfr"] = round(random.uniform(60, 110), 1)
        if random.random() < 0.2:
            p["comorbidities"]["Cardiovascular disease"] = "Yes"
        if random.random() < 0.12:
            p["comorbidities"]["Cancer"] = "Yes"
        p["symptoms"] = random.sample(
            ["Increased thirst", "Frequent urination", "Fatigue", "Blurred vision",
             "Numbness in feet", "Slow healing wounds"], k=random.randint(1, 3))
        if random.random() < 0.3:
            p["previous_treatments"] = ["Sulfonylurea"]
        if gender == "Female":
            p["pregnancy_status"] = random.choice(["Not Pregnant", "Not Pregnant", "Not Pregnant", "Pregnant"])
        p["smoking_status"] = random.choice(["Never", "Never", "Former", "Current"])
        p["alcohol_use"] = random.choice(["Never", "Occasional", "Occasional", "Regular"])

    elif archetype == 3:  # hypertension
        p["condition"] = "Hypertension"
        p["age"] = random.choice([42, 48, 51, 56, 60, 66, 74])
        p["disease_duration_months"] = random.choice([8, 14, 30, 60])
        p["disease_severity"] = random.choice(["Moderate", "Severe"])
        p["systolic_bp"] = round(random.uniform(148, 185))
        p["diastolic_bp"] = round(random.uniform(88, 108))
        p["current_medications"] = [{"name": "Amlodipine", "duration_months": random.choice([6, 12, 24])}]
        p["comorbidities"] = {"Hypertension": "Yes"}
        if random.random() < 0.35:
            p["comorbidities"]["Diabetes"] = "Yes"
            p["hba1c"] = round(random.uniform(6.8, 9.2), 1)
        p["egfr"] = round(random.uniform(35, 100), 1)
        p["symptoms"] = ["Headache", "Dizziness"]

    elif archetype == 5:  # respiratory
        p["condition"] = random.choice(["Asthma", "COPD"])
        p["age"] = random.choice([24, 33, 45, 52, 61, 68])
        p["smoking_status"] = random.choice(["Never", "Former", "Current", "Current"])
        p["current_medications"] = [{"name": "Salbutamol inhaler", "duration_months": 12}]
        p["comorbidities"] = {random.choice(["Asthma", "COPD"]): "Yes"}

    elif archetype == 6:  # arthritis
        p["condition"] = "Rheumatoid Arthritis"
        p["age"] = random.choice([31, 39, 47, 54, 62])
        p["disease_duration_months"] = random.choice([9, 18, 36])
        p["current_medications"] = [{"name": "Methotrexate", "duration_months": random.choice([4, 8, 14])}]
        p["comorbidities"] = {"Autoimmune disease": "Yes"}
        p["symptoms"] = ["Joint pain", "Morning stiffness", "Joint swelling"]

    else:  # healthy volunteer profile
        p["condition"] = None
        p["age"] = random.choice([21, 25, 28, 32, 38, 44])
        p["hba1c"] = round(random.uniform(5.0, 5.6), 1)
        p["systolic_bp"] = round(random.uniform(110, 128))
        p["diastolic_bp"] = round(random.uniform(70, 82))
        p["comorbidities"] = {}
        p["current_medications"] = []
        p["symptoms"] = []
        p["smoking_status"] = random.choice(["Never", "Never", "Former"])
        p["alcohol_use"] = random.choice(["Never", "Occasional"])
        p["prior_trial_participation"] = random.choice(["No", "No", "Unknown"])

    if "egfr" not in p and random.random() < 0.5:
        p["egfr"] = round(random.uniform(55, 118), 1)
    if "hemoglobin" not in p and random.random() < 0.4:
        p["hemoglobin"] = round(random.uniform(8.5, 15.2), 1)
    if "alt" not in p and random.random() < 0.4:
        p["alt"] = round(random.uniform(18, 95), 1)
    p["treatment_failure"] = random.choice(["Unknown", "Unknown", "No", "Yes"])
    p["drug_allergies"] = random.choice([None, None, "Penicillin", "Sulfa drugs"])
    p["prior_trial_participation"] = p.get("prior_trial_participation") or random.choice(["Unknown", "No", "No"])
    return p


def write_patients(n: int = 80) -> list:
    patients = [make_patient(i + 1) for i in range(n)]
    fieldnames = [
        "patient_id", "name", "age", "gender", "state", "city", "height_cm", "weight_kg", "bmi",
        "condition", "disease_duration_months", "disease_severity", "symptoms", "previous_diagnosis",
        "hba1c", "fasting_glucose", "systolic_bp", "diastolic_bp", "egfr", "hemoglobin", "alt",
        "current_medications", "previous_treatments", "comorbidities", "pregnancy_status",
        "smoking_status", "alcohol_use", "treatment_failure", "drug_allergies", "prior_trial_participation",
    ]
    with open(DATA_DIR / "sample_patients.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for p in patients:
            row = dict(p)
            row["symptoms"] = "; ".join(p.get("symptoms", []))
            row["current_medications"] = "; ".join(
                f"{m['name']}" + (f" ({m['duration_months']} mo)" if m.get("duration_months") else "")
                for m in p.get("current_medications", []))
            row["previous_treatments"] = "; ".join(p.get("previous_treatments", []))
            row["comorbidities"] = "; ".join(f"{k}: {v}" for k, v in p.get("comorbidities", {}).items())
            row["pregnancy_status"] = p.get("pregnancy_status", "")
            writer.writerow(row)
    print(f"[data] wrote {n} patients to data/sample_patients.csv")
    return patients


# ---------------------------------------------------------------------------
# 3. Ground truth: does the patient structurally satisfy each trial?
# ---------------------------------------------------------------------------
# This ground truth is produced by an independent, deliberately SIMPLER
# labeller than the eligibility engine, based only on the hard, written
# criteria below. This mimics how trial investigators label eligibility.

TRIAL_LABELLER_RULES = {}  # rules are implemented in label_patient_trial() below


def _age_ok(p, lo, hi):
    a = p.get("age")
    if a is None:
        return None
    return lo <= a <= hi


def _between(v, lo, hi):
    if v is None:
        return None
    return lo <= v <= hi


def label_patient_trial(p: dict, t: dict):
    """Independent labeller implementing each trial's headline criteria."""
    tid = t["trial_id"]
    age = p.get("age")
    a = p.get("hba1c")
    egfr = p.get("egfr")
    bmi = p.get("bmi")
    sbp = p.get("systolic_bp")
    alt_v = p.get("alt")
    comorb = p.get("comorbidities", {})
    preg = p.get("pregnancy_status")
    smoke = p.get("smoking_status")
    alcohol = p.get("alcohol_use")
    cond = (p.get("condition") or "").lower()
    meds = [m["name"].lower() for m in p.get("current_medications", [])]

    def ok(): return True  # noqa: readability helper for labeller branches

    if tid == "CTRI/2024/01/062001":  # T2DM + glimepiride add-on
        checks = [
            _between(age, 30, 65), _between(a, 7.5, 10.5),
            ("metformin" in " ".join(meds)) if meds else None,
            _between(bmi, 23, 35),
        ]
        if preg == "Pregnant": return 0
        if egfr is not None and egfr < 45: return 0
        if any(c is False for c in checks): return 0
        if any(c is None for c in checks): return 2
        return 1

    if tid == "CTRI/2024/02/062115":  # newly diagnosed T2DM
        checks = [_between(age, 25, 60), _between(a, 6.5, 9)]
        if p.get("disease_duration_months") is not None and p["disease_duration_months"] > 6:
            return 0
        if any("insulin" in m for m in meds): return 0
        if egfr is not None and egfr < 60: return 0
        if preg == "Pregnant": return 0
        if any(c is False for c in checks): return 0
        if any(c is None for c in checks): return 2
        return 1

    if tid == "CTRI/2024/03/062318":  # uncontrolled hypertension
        if "hypertension" not in cond and "hypertension" not in comorb: return 0
        if egfr is not None and egfr < 30: return 0
        if preg == "Pregnant": return 0
        checks = [_between(age, 40, 75), _between(sbp, 140, 180)]
        if any(c is False for c in checks): return 0
        if any(c is None for c in checks): return 2
        return 1

    if tid == "CTRI/2024/04/062402":  # HER2+ metastatic breast cancer
        if "breast cancer" not in cond: return 0
        if p.get("gender") != "Female": return 0
        checks = [_between(age, 18, 70)]
        hb, plt = p.get("hemoglobin"), None
        if hb is not None and hb < 9: return 0
        if alt_v is not None and alt_v > 120: return 0
        if preg == "Pregnant": return 0
        if any(c is False for c in checks): return 0
        if any(c is None for c in checks): return 2
        return 1

    if tid == "CTRI/2024/05/062517":  # healthy volunteers
        if p.get("condition"): return 0
        if comorb and any(v == "Yes" for v in comorb.values()): return 0
        if smoke == "Current" or alcohol == "Regular": return 0
        if meds: return 0
        checks = [_between(age, 18, 45), _between(bmi, 18.5, 25)]
        if any(c is False for c in checks): return 0
        if any(c is None for c in checks): return 2
        return 1

    if tid == "CTRI/2024/06/062633":  # yoga add-on T2DM
        if "diabetes" not in cond: return 0
        if egfr is not None and egfr < 30: return 0
        if sbp is not None and sbp > 180: return 0
        checks = [_between(age, 35, 70), _between(a, 7, 10)]
        dur = p.get("disease_duration_months")
        dur_c = (dur >= 12) if dur is not None else None
        if any(c is False for c in checks + [dur_c]): return 0
        if any(c is None for c in checks + [dur_c]): return 2
        return 1

    if tid == "CTRI/2024/07/062744":  # diabetic nephropathy
        if "diabetes" not in cond: return 0
        kd = comorb.get("Kidney disease")
        if kd != "Yes":
            return 0 if kd == "No" else 2
        checks = [_between(age, 30, 75), _between(egfr, 30, 75)]
        if any(c is False for c in checks): return 0
        if any(c is None for c in checks): return 2
        return 1

    if tid == "CTRI/2024/08/062851":  # asthma
        if "asthma" not in cond: return 0
        if smoke == "Current": return 0
        checks = [_between(age, 12, 60)]
        if any(c is False for c in checks): return 0
        if any(c is None for c in checks): return 2
        return 1

    if tid == "CTRI/2024/09/062966":  # RA biologic
        if "rheumatoid" not in cond: return 0
        checks = [_between(age, 18, 65)]
        if preg == "Pregnant": return 0
        if any(c is False for c in checks): return 0
        if any(c is None for c in checks): return 2
        return 1

    if tid == "CTRI/2024/10/063019":  # anaemia in pregnancy
        if p.get("gender") != "Female": return 0
        if preg != "Pregnant": return 0
        return 1 if _between(age, 18, 40) is not False else 0

    if tid == "CTRI/2024/11/063128":  # prediabetes vitamin D
        if "prediabetes" not in cond and "prediabetic" not in cond:
            if a is not None and 5.7 <= a <= 6.4:
                pass
            else:
                return 0
        checks = [_between(age, 30, 60)]
        if egfr is not None and egfr < 60: return 0
        if any(c is False for c in checks): return 0
        if any(c is None for c in checks): return 2
        return 1

    if tid == "CTRI/2024/12/063237":  # T2DM + heart failure
        if "diabetes" not in cond or ("cardiovascular disease" not in comorb and "heart failure" not in cond):
            return 0
        if egfr is not None and egfr < 25: return 0
        checks = [_between(age, 40, 80)]
        if any(c is False for c in checks): return 0
        if any(c is None for c in checks): return 2
        return 1

    if tid == "CTRI/2025/01/063344":  # T2DM + depression
        if "diabetes" not in cond or "depression" not in cond: return 0
        checks = [_between(age, 25, 65)]
        if any(c is False for c in checks): return 0
        if any(c is None for c in checks): return 2
        return 1

    if tid == "CTRI/2025/02/063459":  # rituximab registry
        checks = [_between(age, 18, 80)]
        if any(c is False for c in checks): return 0
        return 1

    if tid == "CTRI/2025/03/063561":  # NAFLD
        if "fatty liver" not in cond and "nafld" not in cond.replace(" ", ""): return 0
        if alcohol == "Regular": return 0
        checks = [_between(age, 25, 55), (bmi > 25) if bmi is not None else None]
        if any(c is False for c in checks): return 0
        if any(c is None for c in checks): return 2
        return 1

    if tid == "CTRI/2025/04/063673":  # COPD triple therapy
        if "copd" not in cond and "chronic obstructive" not in cond: return 0
        checks = [_between(age, 40, 80)]
        if any(c is False for c in checks): return 0
        if any(c is None for c in checks): return 2
        return 1

    if tid == "CTRI/2025/05/063788":  # insulin naive T2DM
        if "diabetes" not in cond: return 0
        if any("insulin" in m for m in meds): return 0
        if egfr is not None and egfr < 30: return 0
        if preg == "Pregnant": return 0
        checks = [_between(age, 18, 70), _between(a, 7.5, 11)]
        if any(c is False for c in checks): return 0
        if any(c is None for c in checks): return 2
        return 1

    if tid == "CTRI/2025/06/063892":  # post-MI telemedicine
        if "myocardial" not in cond and "infarction" not in cond: return 0
        checks = [_between(age, 30, 75)]
        if any(c is False for c in checks): return 0
        if any(c is None for c in checks): return 2
        return 1

    if tid == "CTRI/2025/07/063911":  # vaccination response T2DM
        if "diabetes" not in cond: return 0
        checks = [_between(age, 40, 70), _between(a, 6.5, 10)]
        dur = p.get("disease_duration_months")
        dur_c = (dur >= 24) if dur is not None else None
        if any(c is False for c in checks + [dur_c]): return 0
        if any(c is None for c in checks + [dur_c]): return 2
        return 1

    if tid == "CTRI/2025/08/064022":  # ertugliflozin T2DM obesity
        if "diabetes" not in cond: return 0
        if egfr is not None and egfr < 45: return 0
        if preg == "Pregnant": return 0
        checks = [_between(age, 18, 68), _between(bmi, 30, 45), _between(a, 7.5, 10.5)]
        metf = any("metformin" in m for m in meds)
        if any(c is False for c in checks): return 0
        if any(c is None for c in checks) or metf is False: return 2
        return 1

    return None  # unknown trial -> skip


def write_ground_truth(patients: list) -> None:
    rows = []
    for p in patients:
        for t in TRIALS:
            label = label_patient_trial(p, t)
            if label is None:
                continue
            rows.append({"patient_id": p["patient_id"], "trial_id": t["trial_id"], "actual_label": label})
    with open(DATA_DIR / "sample_ground_truth.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["patient_id", "trial_id", "actual_label"])
        writer.writeheader()
        writer.writerows(rows)
    from collections import Counter
    dist = Counter(r["actual_label"] for r in rows)
    print(f"[data] wrote {len(rows)} ground-truth rows to data/sample_ground_truth.csv {dict(dist)}")


if __name__ == "__main__":
    write_trials()
    patients = write_patients(80)
    write_ground_truth(patients)
    print("[data] done.")
