# Backend — SMART on FHIR Auth Engine (Python/Flask)

A Python/Flask server that handles patient authorization and FHIR data retrieval
against OpenEMR Hospital (a local Dockerized OpenEMR instance), the only data
source this app currently maintains. See "Deprecated data sources" below for
two earlier sources (SMART Health IT Sandbox, local HAPI FHIR) that were
removed since this app only needs real OpenEMR patients now.

## What It Does
1. Redirects patients to OpenEMR Hospital's login page
2. Handles the OAuth 2.0 callback after patient authorizes access
3. Exchanges the authorization code for an access token
4. Uses that token to pull structured clinical records via FHIR R4 APIs, and
   persists them into Store 1 (this app's own MySQL mirror — see storage/)
5. Lets a logged-in patient add/edit/remove conditions and medications,
   which are written to Store 1 first and then mirrored to OpenEMR via its
   native Standard API (see storage/openemr_write.py) — required since
   OpenEMR's FHIR API has no write scope for these resource types

## Tech Stack
- **Language:** Python 3
- **Framework:** Flask
- **HTTP Client:** requests
- **Protocol:** SMART on FHIR (OAuth 2.0)
- **Data Format:** HL7 FHIR R4

## File Structure
backend/

- app.py                          → Main Flask server (port 3000)

- .env                            → Environment variables (not in repo)

- requirements.txt                → Python dependencies

- config/
    * smart.py                    → Data source configurations

- controllers/
    * auth_controller.py          → Auth flow + FHIR data retrieval

- routes/

- auth.py                     → URL routing (Flask Blueprint)

## Setup Instructions

### Prerequisites
- Python 3.9+
- A running HAPI FHIR server (see hapi-fhir-jpaserver-starter folder)

### Create and Activate Virtual Environment
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
```

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Configure Environment
Create a `.env` file in the backend folder (see `.env.example` for the full list —
OpenEMR client/service credentials, Store 1 DB credentials, etc.):

PORT=3000

BASE_URL=http://localhost:3000

`HAPI_FHIR_URL` is no longer read by any active code path — it only applied to
the deprecated local HAPI FHIR source above.

### Start the Server
```bash
python3 app.py
```

### Verify It's Running
Visit: `http://localhost:3000/health`

## Endpoints
| Endpoint | Description |
|----------|-------------|
| `/health` | Confirms the server is running |
| `/connect?source=openemr_hospital` | Initiates SMART on FHIR login flow against OpenEMR Hospital |
| `/callback` | Handles OAuth return, pulls + normalizes + stores records |
| `/session/<session_id>` | Returns the logged-in patient's current record from Store 1 |
| `POST /session/<session_id>/<table>` | Add a condition/medication, pushed to OpenEMR |
| `PUT /session/<session_id>/<table>/<row_id>` | Edit a condition/medication (end + re-add) |
| `DELETE /session/<session_id>/<table>/<row_id>` | End a condition/medication |

## Testing the SMART Auth Flow
1. Visit `http://localhost:3000/connect?source=openemr_hospital` (or click "Log in to OpenEMR Hospital" in the frontend)
2. Log in as a real OpenEMR Hospital user
3. Click Authorize
4. Redirected to the frontend with a session, showing that patient's records

## Data Sources
| Source | Type | Access Method |
|--------|------|---------------|
| OpenEMR Hospital | Local Dockerized EMR | OAuth (SMART on FHIR) for reads; native Standard API for writes |

## Deprecated Data Sources
Removed because this app only maintains OpenEMR Hospital patients now —
documented here for reference, not active in the code. Restore from git
history (this repo's history prior to the OpenEMR-only cleanup) if either
is needed again.

| Source | Type | Access Method | Where it used to live |
|--------|------|----------------|------------------------|
| SMART Health IT Sandbox | Public external test server | OAuth (SMART on FHIR), reached via `/connect?source=sandbox` | Config in `config/smart.py`; no controller code of its own — shared `redirect_to_login`/`handle_callback` |
| Local HAPI FHIR | Locally-run FHIR server seeded with Synthea patients | Unauthenticated direct query by patient name, via `/local` and `/local-clean` | `query_local_fhir`/`query_local_normalized` in `controllers/auth_controller.py`, routed in `routes/auth.py` |

Full config values for both (fhirUrl, scope, etc.) are preserved as a
comment in `config/smart.py` above the current `SMART_CONFIG` dict.

## Resources Currently Retrieved
- Patient (demographics)
- Condition (diagnoses) — read + write
- MedicationRequest (prescriptions) — read + write
- Observation (labs, vitals) — read-only
- AllergyIntolerance (allergies) — read (write gated on OAuth re-scope)
- Immunization (vaccines) — read-only (OpenEMR has no write endpoint)
- Procedure (procedures) — read-only (OpenEMR has no write endpoint)

See `docs/RESOURCE_SYNC_LOG.md` for the per-resource read/write capability
matrix and the history of each fix.

## Notes
- Built with synthetic Synthea data only — no real PHI
- URLs use environment variables for easy deployment 
  (localhost → ngrok → DigitalOcean)

