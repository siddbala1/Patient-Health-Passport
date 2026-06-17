import os
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("BASE_URL", "http://localhost:3000")

SMART_CONFIG = {
    "sandbox": {
        "name": "SMART Health IT Sandbox",
        "fhirUrl": "https://launch.smarthealthit.org/v/r4/sim/WzMsIiIsIiIsIkFVVE8iLDAsMCwwLCIiLCIiLCIiLCIiLCIiLCIiLCIiLDAsMSwiIl0/fhir",
        "clientId": "whatever",
        "redirectUri": f"{BASE_URL}/callback",
        "scope": "openid fhirUser patient/Patient.read patient/Condition.read patient/Observation.read patient/MedicationRequest.read"
    },
    "local": {
        "name": "Local HAPI FHIR",
        "fhirUrl": os.getenv("HAPI_FHIR_URL", "http://localhost:8080/fhir"),
    }
}