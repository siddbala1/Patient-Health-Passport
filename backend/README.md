# Backend — SMART on FHIR Auth Engine (Python/Flask)

A Python/Flask server that handles patient authorization and FHIR data retrieval.
Uses OAuth while sending token requests to "hospitals" (simulated by data repos like HAPI FHIR 
and SMART on FHIR) with fake patient data, and then being authorized to access a JSON file 
with patient resources and medical information



## What It Does
1. Redirects patients to their hospital's login page
2. Handles the OAuth 2.0 callback after patient authorizes access
3. Exchanges the authorization code for an access token
4. Uses that token to pull structured clinical records via FHIR R4 APIs
5. Also supports direct querying of a local HAPI FHIR server

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
Create a `.env` file in the backend folder:

PORT=3000

BASE_URL=http://localhost:3000

HAPI_FHIR_URL=http://localhost:8080/fhir

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
| `/connect?source=sandbox` | Initiates SMART on FHIR login flow |
| `/callback` | Handles OAuth return, pulls records |
| `/local?name=X` | Direct query to local HAPI FHIR by patient name |

## Testing the SMART Auth Flow
1. Visit `http://localhost:3000/connect?source=sandbox`
2. Log in as any test patient on the SMART sandbox page
3. Click Authorize
4. Records returned as JSON

## Data Sources
| Source | Type | Access Method |
|--------|------|---------------|
| SMART Health IT Sandbox | External test environment | OAuth (SMART on FHIR) |
| Local HAPI FHIR | Local fake hospital | Direct query |

## Resources Currently Retrieved
- Patient (demographics)
- Condition (diagnoses)
- MedicationRequest (prescriptions)
- Observation (labs, vitals)

## Notes
- Built with synthetic Synthea data only — no real PHI
- URLs use environment variables for easy deployment 
  (localhost → ngrok → DigitalOcean)

