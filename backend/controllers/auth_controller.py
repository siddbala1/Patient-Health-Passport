from controllers.normalizer import normalize_records
import os
import json
import base64
import uuid
import requests
from flask import request, jsonify, redirect
from config.smart import SMART_CONFIG

# In-memory session store: { session_id: normalized_patient_data }
_sessions = {}

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")


# Step 1: Redirect patient to hospital login page
def redirect_to_login():
    try:
        source = request.args.get("source", "sandbox")
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
        state = request.args.get("state", "sandbox")
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
                "redirect_uri": config["redirectUri"]
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        ).json()

        print("Full token response:", token_response)

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

        session_id = str(uuid.uuid4())
        _sessions[session_id] = clean

        return redirect(f"{FRONTEND_URL}?session={session_id}")

    except Exception as e:
        print(f"Error during callback: {e}")
        return jsonify({"error": "Failed to complete authorization"}), 500


def get_session(session_id):
    data = _sessions.get(session_id)
    if not data:
        return jsonify({"error": "Session not found or expired"}), 404
    return jsonify(data)


# Step 3: Pull FHIR records using access token
def pull_patient_records(patient_id, token, fhir_url):
    headers = {"Authorization": f"Bearer {token}"}

    patient = requests.get(f"{fhir_url}/Patient/{patient_id}", headers=headers).json()
    conditions = requests.get(f"{fhir_url}/Condition?patient={patient_id}", headers=headers).json()
    medications = requests.get(f"{fhir_url}/MedicationRequest?patient={patient_id}", headers=headers).json()
    observations = requests.get(f"{fhir_url}/Observation?patient={patient_id}", headers=headers).json()
    #Other resources can be added in the future: allgergies = requests.get(f"{fhir_url}/AllergyIntolerance?patient={patient_id}", headers=headers).json()
    #immunizations = requests.get(f"{fhir_url}/Immunization?patient={patient_id}", headers=headers).json()
    #etc.


    return {
        "patient": patient,
        "conditions": conditions,
        "medications": medications,
        "observations": observations
    }


# Query local HAPI FHIR server directly (no auth needed)
def query_local_fhir():
    try:
        name = request.args.get("name")

        if not name:
            return jsonify({
                "error": "Please provide a patient name",
                "example": "http://localhost:3000/local?name=Walton"
            }), 400

        fhir_url = os.getenv("HAPI_FHIR_URL")

        parts = name.strip().split()
        patient = None
        if len(parts) >= 2:
            # Try given + family search first
            given, family = parts[0], parts[-1]
            res = requests.get(f"{fhir_url}/Patient?given={given}&family={family}").json()
            if res.get("total", 0) > 0:
                patient = res["entry"][0]["resource"]

        if not patient:
            res = requests.get(f"{fhir_url}/Patient?name={parts[0]}").json()
            if res.get("total", 0) > 0:
                patient = res["entry"][0]["resource"]

        if not patient:
            return jsonify({"error": f"No patient found with name: {name}"}), 404

        patient_id = patient["id"]
        print(f"Found local patient: {patient['name'][0]['family']}, ID: {patient_id}")

        conditions = requests.get(f"{fhir_url}/Condition?patient={patient_id}").json()
        medications = requests.get(f"{fhir_url}/MedicationRequest?patient={patient_id}").json()
        observations = requests.get(f"{fhir_url}/Observation?patient={patient_id}").json()

        return jsonify({
            "message": "Successfully retrieved records from local HAPI FHIR",
            "source": "Local HAPI FHIR Server",
            "patientId": patient_id,
            "records": {
                "patient": patient,
                "conditions": conditions,
                "medications": medications,
                "observations": observations
            }
        })

    except Exception as e:
        print(f"Error querying local FHIR: {e}")
        return jsonify({"error": "Failed to query local FHIR server"}), 500

# Query local HAPI FHIR and return NORMALIZED (clean) data
def query_local_normalized():
    try:
        name = request.args.get("name")

        if not name:
            return jsonify({
                "error": "Please provide a patient name",
                "example": "http://localhost:3000/local-clean?name=Walton"
            }), 400

        fhir_url = os.getenv("HAPI_FHIR_URL")

        parts = name.strip().split()
        patient = None
        if len(parts) >= 2:
            given, family = parts[0], parts[-1]
            res = requests.get(f"{fhir_url}/Patient?given={given}&family={family}").json()
            if res.get("total", 0) > 0:
                patient = res["entry"][0]["resource"]

        if not patient:
            res = requests.get(f"{fhir_url}/Patient?name={parts[0]}").json()
            if res.get("total", 0) > 0:
                patient = res["entry"][0]["resource"]

        if not patient:
            return jsonify({"error": f"No patient found with name: {name}"}), 404

        patient_id = patient["id"]

        conditions = requests.get(f"{fhir_url}/Condition?patient={patient_id}").json()
        medications = requests.get(f"{fhir_url}/MedicationRequest?patient={patient_id}").json()
        observations = requests.get(f"{fhir_url}/Observation?patient={patient_id}").json()

        raw = {
            "source": "Local HAPI FHIR Server",
            "patientId": patient_id,
            "records": {
                "patient": patient,
                "conditions": conditions,
                "medications": medications,
                "observations": observations,
            }
        }

        clean = normalize_records(raw)
        return jsonify(clean)

    except Exception as e:
        print(f"Error in query_local_normalized: {e}")
        return jsonify({"error": "Failed to query and normalize"}), 500

##serves as a new endpoint that queries the local HAPI FHIR server for a patient by name, 
##retrieves their records, and then normalizes the data before returning it to the frontend. 
##This allows the frontend to receive a clean, consistent structure regardless of the quirks in the raw FHIR data.