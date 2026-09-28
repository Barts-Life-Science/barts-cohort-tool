# Cohort Definition Builder

This project has two parts:
- A **backend API** using Python FastAPI framework
  - Code under /app 
- A **web frontend** using React
  - Code under /frontend


## Prerequisites
- Python 3.x installed
- `pip` and `virtualenv` or `venv` available


## Development Setup
For the development setup:
- create a terminal for the frontend
- cd to the frontend directory
- run `npm start` for automatic reloading react app on http://localhost:3000
- create a second terminal for the backend
- run `uvicorn app.main:app --reload` for automatic reloading backend on http://localhost:8000
- The frontend app will proxy the backend app so all can be accessed on port 3000.

## Production Setup
For the production setup we build the frontend and serve it from the backend:
- In a terminal cd to the frontend directory
- run `npm run buld` to create the static files
- cd back to the project root
- run `uvicorn app.main:app` to start the backend on http://localhost:8000
- The frontend app will be served by the backend on port 8000.
- Use a web proxy server like Nginx or Apache2 to add SSL and any required authentication. 

## API Setup Instructions

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```

2. Create the virtual environment
    ```bash
    python -m venv .venv
    ```

3. Activate the virtual environment:

    **__Linux/MacOS:__**
    ```bash
    source .venv/bin/activate
    ```
    **Windows:**
    ```bash
    .venv\Scripts\activate
    ```

4. Install dependencies:
    ```bash
    pip install -r requirements.txt
   ```

5. Run the application:
    ```bash
    uvicorn app.main:app --reload
    ```

## Cohort data (gold)

Cohort counts are computed against Azure SQL tables loaded from the Databricks
`4_prod.gold` layer by the **SNOMED COHORT BROWSER** ADF pipeline (ADC-DF):

| Table | Gold source | Grain |
|---|---|---|
| `cohort.person` | `gold.spine_person` | person: `birth_year`, NHS gender code (`1`/`2`/`X`), NHS ethnic category (`A`–`S`, `Z`, `99`) |
| `cohort.condition` | `gold.clinical_condition` | coded condition event: `snomed_code`, `condition_datetime` |
| `cohort.admission` | `gold.spine_encounter` (`encounter_level = 'spell'`) | inpatient spell: `admit_datetime`, `discharge_datetime` |
| `cohort.procedure_event` | `gold.clinical_procedure` | procedure: `snomed_code`, `device_snomed_code` (implants), `procedure_datetime`, `encounter_id` |
| `cohort.medication_admin` | `gold.clinical_medication_admin` | administration: `snomed_code`, `administration_datetime`, `administration_status` (e.g. `Not Done`, `In Error`), `encounter_id` |

`procedure_event` and `medication_admin` are loaded for upcoming procedure/medication criteria and are
not queried yet. Their `snomed_code` is NULL where gold has no SNOMED mapping (about 9% of procedures,
18% of administrations); those rows update in place when a mapping arrives.

Every row carries gold's `record_status`; searches count `active` rows only. The pipeline
loads incrementally on a watermark (`mode=incremental`, 72h lookback) into `cohort_stage`
and MERGEs into `cohort`; run it with `mode=full` periodically to pick up deletions.

`DW_CONNECTION` must point at that database. `COHORT_SCHEMA` (default `cohort`) selects the
schema. The old `SQL_QUERY` / `SQL_QUERY_NOT_HAVE` settings are no longer used and are ignored
if still present in `.env`.

Search semantics:
- Gender and ethnicity filters match on the NHS codes sent by the frontend.
- A patient needs an admission only when an admission timeframe is set.
- Must-have findings: at least one block matches (each block = its codes within its timeframe).
  Must-not-have findings: no block matches. Timeframe end dates are inclusive.
- Counts are aggregated in SQL; the response no longer includes row-level `results`.
  "Total encounters" is the number of admissions of the cohort (in the admission timeframe, if set);
  diagnosis counts are condition records per must-have code.
