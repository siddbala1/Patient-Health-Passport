import os
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("BASE_URL", "http://localhost:3000")

# --- Deprecated sources (archived, not active) ---------------------------
# This app now only talks to OpenEMR Hospital: it's the only source that can
# receive writes (via openemr_write below), so it's the only one worth
# keeping wired up. Two earlier sources are documented here for reference
# rather than left as dead code:
#
#   "sandbox" — SMART Health IT's public test server. Config was:
#     name: "SMART Health IT Sandbox"
#     fhirUrl: "https://launch.smarthealthit.org/v/r4/sim/WzMsIiIsIiIsIkFVVE8iLDAsMCwwLCIiLCIiLCIiLCIiLCIiLCIiLCIiLDAsMSwiIl0/fhir"
#     clientId: "whatever"  (public sandbox, no real registration needed)
#     redirectUri: f"{BASE_URL}/callback"
#     scope: "openid fhirUser patient/Patient.read patient/Condition.read
#             patient/Observation.read patient/MedicationRequest.read"
#     Reached the login page via /connect?source=sandbox, same OAuth
#     handshake as openemr_hospital below.
#
#   "local" — a locally-run HAPI FHIR server seeded with Synthea patients,
#   queried directly by name with no auth (see the old query_local_fhir /
#   query_local_normalized functions, previously in auth_controller.py, and
#   the /local, /local-clean routes, previously in routes/auth.py). Config
#   was just:
#     name: "Local HAPI FHIR"
#     fhirUrl: os.getenv("HAPI_FHIR_URL", "http://localhost:8080/fhir")
#
# Both are gone now because this app only maintains OpenEMR patients going
# forward — restore from git history if either is needed again.

SMART_CONFIG = {
    "openemr_hospital": {
        "name": "OpenEMR Hospital (Simulated)",
        "authorizeUrl": "http://localhost:8301/oauth2/default/authorize",
        "tokenUrl": "http://localhost:8301/oauth2/default/token",
        "fhirUrl": "http://localhost:8301/apis/default/fhir",
        "clientId": os.getenv("OPENEMR_HOSPITAL_CLIENT_ID"),
        "clientSecret": os.getenv("OPENEMR_HOSPITAL_CLIENT_SECRET"),
        "redirectUri": f"{BASE_URL}/callback",
        "scope": "openid fhirUser launch/patient offline_access patient/Patient.read patient/Condition.read patient/Observation.read patient/MedicationRequest.read patient/AllergyIntolerance.read patient/Immunization.read patient/Procedure.read"
    },
    # Write-back path: same instance as openemr_hospital (patients live on
    # :8301), but a separate registered OAuth2 client using the password
    # grant, since OpenEMR's FHIR API has no write scopes for these
    # resource types. Writes go through OpenEMR's native Standard API
    # (/apis/default/api) instead of /apis/default/fhir.
    "openemr_write": {
        "name": "OpenEMR Hospital Write Client",
        "tokenUrl": "http://localhost:8301/oauth2/default/token",
        "apiUrl": "http://localhost:8301/apis/default/api",
        "clientId": os.getenv("OPENEMR_WRITE_CLIENT_ID"),
        "clientSecret": os.getenv("OPENEMR_WRITE_CLIENT_SECRET"),
        "serviceUser": os.getenv("OPENEMR_SERVICE_USER"),
        "servicePassword": os.getenv("OPENEMR_SERVICE_PASSWORD"),
        "scope": "openid offline_access api:oemr user/medical_problem.read user/medical_problem.write user/medication.read user/medication.write user/allergy.read user/allergy.write user/patient.read user/patient.write"
    }
}