import os
import json
import base64
import requests
from flask import request, jsonify, redirect
from config.smart import SMART_CONFIG


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

        # Fetch token endpoint
        smart_config = requests.get(
            f"{config['fhirUrl']}/.well-known/smart-configuration"
        ).json()

        token_endpoint = smart_config["token_endpoint"]

        # Exchange code for access token
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
        patient = token_response.get("patient")

        # If patient ID not returned directly, extract from token
        if not patient:
            fhir_user = token_response.get("fhirUser")
            if not fhir_user:
                # Decode the JWT middle section to find fhirUser
                payload = access_token.split(".")[1]
                payload += "=" * (-len(payload) % 4)  # fix padding
                decoded = json.loads(base64.b64decode(payload))
                fhir_user = decoded.get("fhirUser")

            patient_id = fhir_user.split("/")[1] if fhir_user else None
            print(f"Extracted patient ID: {patient_id}")

            if patient_id:
                records = pull_patient_records(patient_id, access_token, config["fhirUrl"])
                return jsonify({
                    "message": "Successfully connected and retrieved records",
                    "patientId": patient_id,
                    "records": records
                })

            return jsonify({
                "message": "Authorization successful",
                "access_token": access_token,
                "note": "Patient ID not returned by sandbox - token exchange worked correctly"
            })

        print(f"Token received for patient: {patient}")
        records = pull_patient_records(patient, access_token, config["fhirUrl"])

        return jsonify({
            "message": "Successfully connected and retrieved records",
            "patientId": patient,
            "records": records
        })

    except Exception as e:
        print(f"Error during callback: {e}")
        return jsonify({"error": "Failed to complete authorization"}), 500


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

        patient_search = requests.get(f"{fhir_url}/Patient?name={name}").json()

        if patient_search.get("total", 0) == 0:
            return jsonify({"error": f"No patient found with name: {name}"}), 404

        patient = patient_search["entry"][0]["resource"]
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