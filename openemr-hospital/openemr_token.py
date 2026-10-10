import requests, os

def get_openemr_write_token():
    resp = requests.post(
        "http://localhost:8301/oauth2/default/token",
        data={
            "grant_type": "password",
            "client_id": os.getenv("OPENEMR_WRITE_CLIENT_ID"),
            "client_secret": os.getenv("OPENEMR_WRITE_CLIENT_SECRET"),
            "user_role": "users",
            "username": os.getenv("OPENEMR_SERVICE_USER"),
            "password": os.getenv("OPENEMR_SERVICE_PASSWORD"),
            "scope": "openid offline_access api:oemr user/medical_problem.write user/medication.write user/patient.write",
        },
        verify=False,
    )

    print("Status:", resp.status_code)
    print("Response:", resp.text)

    resp.raise_for_status()
    return resp.json()["access_token"]

token = get_openemr_write_token()
print("Got token:", token[:20] + "...")