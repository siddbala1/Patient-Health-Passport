from controllers.normalizer import normalize_records
from storage.store import save_normalized_records
from storage.queries import get_patient_record
import os
import json
import base64
import uuid
import requests
from flask import request, jsonify, redirect
from config.smart import SMART_CONFIG

# In-memory session store: { session_id: patient_id }.
# The session no longer holds patient data directly — Store 1 (MySQL) is the
# source of truth, this just remembers which patient a session points to.
_sessions = {}

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")


# Step 1: Redirect patient to hospital login page
def redirect_to_login():
    try:
        source = request.args.get("source", "openemr_hospital")
        config = SMART_CONFIG[source]

        # Fetch the hospital's SMART configuration
        smart_config = requests.get(
            f"{config['fhirUrl']}/.well-known/smart-configuration"
        ).json()

        authorization_endpoint = smart_config["authorization_endpoint"]
    ##Constructs parameters for the authorization endpoint and 
    ##What the smart configuration is using abstract defintiions
        # Build the login URL
        params = {
            "response_type": "code",
            "client_id": config["clientId"],
            "redirect_uri": config["redirectUri"],
            "scope": config["scope"],
            "state": source,
            "aud": config["fhirUrl"]
        }

        query = "&".join([f"{k}={requests.utils.quote(str(v))}" for k, v in params.items()])
        login_url = f"{authorization_endpoint}?{query}"

        print(f"Redirecting patient to: {login_url}")
        return redirect(login_url)

    except Exception as e:
        print(f"Error during login redirect: {e}")
        return jsonify({"error": "Failed to initiate login"}), 500


# Step 2: Handle callback after patient logs in
def handle_callback():
    try:
        code = request.args.get("code")
        state = request.args.get("state", "openemr_hospital")
        config = SMART_CONFIG[state]

        smart_config = requests.get(
            f"{config['fhirUrl']}/.well-known/smart-configuration"
        ).json()

        token_endpoint = smart_config["token_endpoint"]

        token_response = requests.post(
            token_endpoint,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": config["clientId"],
                "client_secret": config["clientSecret"],
                "redirect_uri": config["redirectUri"]
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        ).json()

        access_token = token_response.get("access_token")
        patient_id = token_response.get("patient")

        # Extract patient ID from JWT if not returned directly
        if not patient_id:
            fhir_user = token_response.get("fhirUser")
            if not fhir_user:
                payload = access_token.split(".")[1]
                payload += "=" * (-len(payload) % 4)
                decoded = json.loads(base64.b64decode(payload))
                fhir_user = decoded.get("fhirUser")
            patient_id = fhir_user.split("/")[1] if fhir_user else None

        if not patient_id:
            return jsonify({"error": "Could not determine patient ID from token"}), 400

        print(f"Token received for patient: {patient_id}")

        raw_records = pull_patient_records(patient_id, access_token, config["fhirUrl"])

        raw = {
            "source": config.get("name", "SMART on FHIR"),
            "patientId": patient_id,
            "records": raw_records,
        }
        clean = normalize_records(raw)
        save_normalized_records(patient_id, clean)

        session_id = str(uuid.uuid4())
        _sessions[session_id] = patient_id

        return redirect(f"{FRONTEND_URL}?session={session_id}")

    except Exception as e:
        print(f"Error during callback: {e}")
        return jsonify({"error": "Failed to complete authorization"}), 500


def get_session(session_id):
    patient_id = _sessions.get(session_id)
    if not patient_id:
        return jsonify({"error": "Session not found or expired"}), 404

    record = get_patient_record(patient_id)
    if not record:
        return jsonify({"error": "No stored record for this patient"}), 404
    return jsonify(record)


def get_session_patient_id(session_id):
    """Resolve a session to the patient_id it points to, for other
    controllers (e.g. records_controller) that need to act on behalf of a
    logged-in patient without reaching into _sessions directly."""
    return _sessions.get(session_id)


# Step 3: Pull FHIR records using access token
def pull_patient_records(patient_id, token, fhir_url):
    headers = {"Authorization": f"Bearer {token}"}

    patient = requests.get(f"{fhir_url}/Patient/{patient_id}", headers=headers).json()
    conditions = requests.get(f"{fhir_url}/Condition?patient={patient_id}", headers=headers).json()
    print("RAW CONDITION JSON:", conditions)
    ##Addresses issues with redirect and condition fetching in OpenEMR instance
    medications = requests.get(f"{fhir_url}/MedicationRequest?patient={patient_id}", headers=headers).json()
    observations = requests.get(f"{fhir_url}/Observation?patient={patient_id}", headers=headers).json()
    # Allergies, immunizations, and procedures — all read-only pulls. The
    # OpenEMR read client is already registered for these FHIR scopes; the
    # requested scope string in config/smart.py was widened to match.
    # Immunizations and procedures have no OpenEMR write endpoint (Standard
    # API 404s), so they flow OpenEMR → Passport only.
    allergies = requests.get(f"{fhir_url}/AllergyIntolerance?patient={patient_id}", headers=headers).json()
    immunizations = requests.get(f"{fhir_url}/Immunization?patient={patient_id}", headers=headers).json()
    procedures = requests.get(f"{fhir_url}/Procedure?patient={patient_id}", headers=headers).json()
    # Clinical notes (progress notes etc.) come back as DocumentReference.
    documents = requests.get(f"{fhir_url}/DocumentReference?patient={patient_id}", headers=headers).json()

    return {
        "patient": patient,
        "conditions": conditions,
        "medications": medications,
        "observations": observations,
        "allergies": allergies,
        "immunizations": immunizations,
        "procedures": procedures,
        "documents": documents,
    }


# query_local_fhir() and query_local_normalized() (direct, unauthenticated
# queries against a local HAPI FHIR server by patient name, backing the
# removed /local and /local-clean routes) were removed — this app now only
# maintains OpenEMR Hospital patients. See config/smart.py's "Deprecated
# sources" comment for their original config; restore from git history if
# HAPI FHIR support is needed again.