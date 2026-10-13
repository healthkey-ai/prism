# PRism

[![Tests](https://github.com/healthkey-ai/prism/actions/workflows/test.yml/badge.svg)](https://github.com/healthkey-ai/prism/actions/workflows/test.yml)
[![DOI](https://joss.theoj.org/papers/10.21105/joss.XXXXX/status.svg)](https://doi.org/10.21105/joss.XXXXX)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

Real-world evidence analytics for oncology patient cohorts, built on top of [PROMOP](https://github.com/healthkey-ai/promop) (OMOP CDM 5.4).

## Overview

Select a patient cohort using 20+ clinical criteria, then instantly explore outcomes across response rates, treatment patterns, demographics, disease staging, lab values, and more — all derived from structured real-world data in a PostgreSQL OMOP CDM database.

## Features

### Cohort Builder
Filter patients by:
- Disease (Multiple Myeloma, Breast Cancer, Follicular Lymphoma)
- ISS stage, ECOG performance status
- Age range, gender, ethnicity, geographic region
- Cytogenetic markers (del17p, t(4;14), t(14;16), high-risk flag, TP53 disruption)
- Lines of therapy (min/max), 1L/2L/3L+ regimen and outcome
- Refractory status
- MM-specific: CRAB criteria, bone lesions, prior ASCT, plasma cell leukemia
- Lab ranges: hemoglobin, β2-microglobulin, albumin, creatinine
- Diagnosis year range, smoking status

### Cohort Characterization (Table 1)
- **Cohort summary** — structured Table 1 with age (median, Q1/Q3), sex, receptor status (ER+/HER2+/TNBC), stage distribution, ECOG, MRD status, 2L/3L treatment rates, and key lab values
- **Current disease state** — mutually exclusive classification into Relapsed/Refractory, In Remission, Watch & Wait, Newly Diagnosed, or Other/Unknown
- **Eligibility funnel** — step-by-step patient counts showing how many patients remain after each filter criterion
- **Incidence over time** — quarterly time series of new diagnoses and treatment starts

### Survival & Time-to-Event
- **Overall Survival (OS)** — Kaplan-Meier from first-line start to death
- **Progression-Free Survival (PFS)** — KM from first-line start to first progression or death
- **Event-Free Survival (EFS)** — KM from first-line start to treatment change, 1L progression, or death
- **Duration of Response (DOR)** — KM restricted to confirmed responders (CR/sCR/VGPR/PR/MR), first and second line
- **Landmark OS** — OS restricted to patients surviving past a configurable landmark (default 6 months), time-shifted KM
- **POD24** — Progression within 24 months of 1L; classifies patients and compares OS via 24-month landmark analysis
- **Subgroup survival** — stratified KM (OS + PFS) by ISS/R-ISS stage, cytogenetic risk (High vs. Standard), SCT status, and MRD status; log-rank p-values per split
- **Forest plot** — per-subgroup OS hazard ratios with 95% CI (Peto method) across cytogenetic risk, stage, SCT, age ≥65, and MRD status
- **Time-to-Next-Therapy (TTNT)** — KM from end of 1L to start of 2L, and from end of 2L to start of 3L+
- **Time to treatment** — diagnosis-to-first-treatment delay: median days and histogram
- **Treatment duration** — per-therapy median and mean duration (months) by line; diagnosis-to-1L start distribution

### Treatment Patterns
- **Line-of-therapy breakdown** — therapy counts and percentages at first, second, and later lines; overall counts across any line
- **Treatment burden** — line funnel (≥1L through ≥4L), median lines of therapy, ≥2L% and ≥3L%
- **Top treatment sequences** — most common 1L → 2L → 3L therapy paths (top 12), e.g. VRd → Daratumumab → Cilta-cel
- **Treatment switching flows** — regimen-to-regimen switching from 1L→2L and 2L→3L+ with counts and percentages
- **Pathway sunburst** — hierarchical 1L → 2L → 3L treatment pathway tree
- **Pathway outcomes** — OS curves for the top 5 (1L → 2L) treatment pathways (≥10 patients each)

### Response & Outcomes
- **Response rates** — CR, VGPR, PR, MR, SD, PD counts and ORR (CR+VGPR+PR%) per therapy at each line; chart/table toggle
- **Landmark response** — CR rate at configurable landmarks (default 12, 24, 30, 36 months from 1L start)
- **Therapy categories** — Bispecific antibody, CAR-T, ADC, chemotherapy, IMiD, monoclonal antibody, targeted/small molecule, and endocrine agent counts per line

### Demographics & Staging
- **Patient demographics** — age bucket histogram, gender donut, race, ethnicity, and geographic distribution (top 15 regions), smoking status
- **Disease staging** — ISS/R-ISS stage distribution, ECOG performance status, CRAB criteria, cytogenetic marker breakdown (del(17p), t(4;14), t(14;16), 1q21, hyperdiploidy; high-risk highlighted), SCT rate, bone lesion types, refractory status
- **Laboratory values** — box plots (median/IQR/range) for hemoglobin, β2-microglobulin, albumin, creatinine, LDH, M-protein, calcium, and kappa/lambda FLC

### Disease-Specific Panels
- **FL → DLBCL transformation** *(Follicular Lymphoma only)* — transformation rate, time-to-transformation histogram, post-transformation outcome distribution, and OS from transformation date

## Stack

| Layer | Technology |
|---|---|
| Backend | Django 5 + Django REST Framework |
| Database | PostgreSQL (OMOP CDM 5.4) via PROMOP |
| Frontend | React 19 + TypeScript + Vite |
| Styling | Tailwind CSS v4 |
| Charts | Recharts |

## Project Structure

```
prism/
├── backend/                    # Django + DRF API
│   ├── analytics_project/      # Django project settings and URLs
│   ├── accounts/               # Identity model, JWT auth
│   ├── patients/               # Unmanaged PatientRecord read model (reads patient_record table)
│   ├── cohorts/                # Cohort filter logic, saved views, disease normalization
│   └── metrics/                # Analytics computation services
│       ├── views.py            # /api/metrics/ endpoint
│       ├── tests/              # pytest tests per service
│       └── services/
│           ├── survival.py           # OS / PFS / EFS KM curves
│           ├── subgroup_survival.py  # Stratified KM by stage / cyto / SCT / MRD
│           ├── dor.py                # Duration of Response
│           ├── pod24.py              # Progression within 24 months
│           ├── forest_plot.py        # Hazard ratios with 95% CI
│           ├── ttnt.py               # Time-to-Next-Therapy
│           ├── time_to_treatment.py  # Diagnosis-to-treatment delay
│           ├── treatment_duration.py # Per-therapy duration by outcome
│           ├── landmark_response.py  # CR rate at landmark timepoints
│           ├── treatment_patterns.py # Line breakdown, sequences, burden
│           ├── switching.py          # Regimen-to-regimen switching flows
│           ├── pathway_sunburst.py   # Hierarchical pathway tree
│           ├── pathway_outcomes.py   # OS per top pathway
│           ├── response_rates.py     # ORR / CR / VGPR / PR by therapy
│           ├── therapy_categories.py # MOA category counts per line
│           ├── demographics.py       # Age, sex, race, region
│           ├── cohort_characterization.py  # Table 1
│           ├── staging.py            # Stage, ECOG, cyto, SCT, CRAB
│           ├── labs.py               # Lab value distributions
│           ├── disease_state.py      # Current disease state classification
│           ├── eligibility.py        # Filter funnel
│           ├── incidence.py          # Quarterly diagnosis/treatment trends
│           ├── transformation.py     # FL → DLBCL transformation (FL only)
│           └── km_utils.py           # Shared KM estimator
├── frontend/                   # React SPA
│   └── src/
│       ├── components/
│       │   ├── CohortPanel/    # Dark sidebar with collapsible filter sections
│       │   ├── Dashboard/      # Main layout with sticky header
│       │   ├── charts/         # One component per dashboard panel
│       │   └── ui/             # MetricCard wrapper
│       ├── hooks/
│       │   └── useAnalytics.ts # State management + 400ms debounced API calls
│       ├── api/client.ts       # Axios client + filter serialization
│       ├── utils/kmChartUtils.ts  # mergeKMCurves shared utility
│       └── types/index.ts      # Shared TypeScript interfaces
└── seed_mm_patients.py         # Seeds 100 realistic MM patients into PROMOP
```

## Getting Started

### Backend

```bash
cd backend
pip install -r requirements.txt
python manage.py runserver
```

The API is available at `http://localhost:8000/api/`.

Key endpoints:
- `GET /api/form-settings/?disease=Multiple+Myeloma` — returns therapy lists, staging options, etc. for the cohort builder
- `GET /api/metrics/?disease=Multiple+Myeloma&[filters...]` — returns all dashboard metrics for the current cohort

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The app is available at `http://localhost:5173/`. API requests to `/api/*` are proxied to the Django backend at `http://localhost:8000`.

### Seeding Sample Data

The recommended way to populate a PROMOP database with synthetic oncology patients is via PROMOP's built-in FHIR pipeline. See the [PROMOP quickstart guide](https://github.com/healthkey-ai/promop/blob/dev/docs/quickstart.md) for full instructions. In short:

```bash
# Generate a synthetic FHIR bundle
python manage.py generate_fhir_bundle --patients 100 --disease MM

# Import the bundle into the PROMOP database
python manage.py import_fhir_bundle bundle.json
```

Alternatively, the repository includes a standalone seed script for 100 Multiple Myeloma patients with clinically plausible treatment histories and outcome distributions drawn from published trial data (GRIFFIN, MAIA, KarMMa, CARTITUDE-1, DREAMM-2, etc.), risk-adjusted for high-risk cytogenetics:

```bash
DATABASE_URL="postgresql://..." python seed_mm_patients.py
```

## Deploying to Render

**Root Directory:** `backend`

**Build Command:**
```
pip install -r requirements.txt && python manage.py collectstatic --noinput
```

**Start Command:**
```
gunicorn analytics_project.wsgi:application --bind 0.0.0.0:$PORT
```

**Environment variables:**
| Variable | Value |
|---|---|
| `DEBUG` | `false` |
| `SECRET_KEY` | *(generate a random secret)* |
| `CORS_ALLOWED_ORIGINS` | `https://your-frontend.onrender.com` |
| `CYTOGENETIC_MARKERS_DB_COLUMN` | `cytogenetic_markers` after PROMOP migration 0222; defaults to `cytogenic_markers` for older databases |

## Database

The backend connects to a PROMOP PostgreSQL instance and reads PatientRecord data from the `patient_record` table via an unmanaged Django model. Connection settings live in `backend/analytics_project/settings.py`.

## Citing PRism

If you use PRism in research, please cite:

> Blum, A. (2026). PRism: An Open-Source Real-World Evidence Analytics Platform for Oncology Patient Cohorts. *Journal of Open Source Software*. https://doi.org/10.21105/joss.XXXXX
