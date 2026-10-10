# Write-back path: mirrors a Store 1 clinical write to OpenEMR's native
# Standard API (/apis/default/api), for resources whose entry in
# storage/resources.py has an "openemr" block. Driven entirely by that
# registry so a new resource type is a config addition, not new code here.
#
# Not called from the passive OpenEMR-read sync (store.py's
# _sync_versioned during login/record-pull) — only from patient-initiated
# writes, to avoid immediately re-pushing back data that was just read in.

import time
import requests
from config.smart import SMART_CONFIG

_token_cache = {"access_token": None, "expires_at": 0}
_pid_cache = {}  # Store 1 patient_id (uuid) -> OpenEMR's internal numeric id


def _config():
    return SMART_CONFIG["openemr_write"]


def _get_token():
    if _token_cache["access_token"] and _token_cache["expires_at"] > time.time() + 30:
        return _token_cache["access_token"]

    config = _config()
    resp = requests.post(
        config["tokenUrl"],
        data={
            "grant_type": "password",
            "client_id": config["clientId"],
            "client_secret": config["clientSecret"],
            "user_role": "users",
            "username": config["serviceUser"],
            "password": config["servicePassword"],
            "scope": config["scope"],
        },
    )
    resp.raise_for_status()
    body = resp.json()
    _token_cache["access_token"] = body["access_token"]
    _token_cache["expires_at"] = time.time() + body.get("expires_in", 3600)
    return _token_cache["access_token"]


def _headers():
    return {
        "Authorization": f"Bearer {_get_token()}",
        "Content-Type": "application/json",
    }


def _resolve_pid(patient_id):
    """Store 1 keys patients by OpenEMR's FHIR/Standard-API uuid, but some
    Standard API resources (e.g. medication) address the patient by
    OpenEMR's internal numeric id instead. Resolve and cache that mapping."""
    if patient_id in _pid_cache:
        return _pid_cache[patient_id]
    resp = requests.get(
        f"{_config()['apiUrl']}/patient/{patient_id}", headers=_headers()
    )
    resp.raise_for_status()
    pid = resp.json()["data"]["id"]
    _pid_cache[patient_id] = pid
    return pid


def _patient_path(patient_id, id_style):
    return patient_id if id_style == "uuid" else _resolve_pid(patient_id)


def _format_date(openemr_spec, oe_field, value):
    """Endpoints disagree on date format: medication (via ListService)
    requires a full "Y-m-d H:i:s" datetime and 400s on a plain "Y-m-d" date,
    while medical_problem (via ConditionValidator) requires the opposite.
    See resources.py's "datetime_fields" doc comment for the source refs."""
    if value and oe_field in openemr_spec.get("datetime_fields", ()) and len(value) == 10:
        return f"{value} 00:00:00"
    return value


def _format_body(openemr_spec, row):
    body = {}
    for local_field, oe_field in openemr_spec["fields"].items():
        body[oe_field] = _format_date(openemr_spec, oe_field, row.get(local_field))
    return body


def push_create(patient_id, spec, row, extra_fields=None):
    """Create a new record in OpenEMR for a freshly-inserted Store 1 row.
    Returns the OpenEMR-side id to persist as that row's openemr_id, or
    None if this resource type isn't configured to push.

    extra_fields lets a caller add request-body fields that don't come from
    a Store 1 column — e.g. records_controller.py resolving a condition's
    name to an ICD-10 code and passing it as {"diagnosis": "ICD10:..."},
    since OpenEMR's FHIR Condition mapping only ever carries a diagnosis
    code, never the free-text title we'd otherwise send as "title"."""
    openemr_spec = spec.get("openemr")
    if not openemr_spec:
        return None

    path_id = _patient_path(patient_id, openemr_spec["id_style"])
    body = _format_body(openemr_spec, row)
    if extra_fields:
        body.update(extra_fields)

    resp = requests.post(
        f"{_config()['apiUrl']}/patient/{path_id}/{openemr_spec['list_type']}",
        json=body,
        headers=_headers(),
    )
    resp.raise_for_status()
    # ConditionRestController wraps its response in {"data": {...}}; the
    # generic ListRestController (medication, and any future list-backed
    # resource) returns the id flat at the top level instead.
    payload = resp.json()
    data = payload["data"] if isinstance(payload.get("data"), dict) else payload
    return str(data.get("uuid") or data.get("id"))


def push_end(patient_id, spec, openemr_id, row, end_date, extra_fields=None):
    """Mark the OpenEMR-side record ended (patients ending a condition or
    stopping a medication), matching Store 1's own non-destructive
    versioning — never a hard delete on the OpenEMR side either.

    OpenEMR's endpoints disagree on whether PUT accepts a partial update:
    medical_problem does, but medication's generic list-update validator
    requires "title" on every PUT, not just changed fields. Resending the
    row's own fields alongside enddate satisfies both without needing to
    special-case per resource. See push_create() for what extra_fields is."""
    openemr_spec = spec.get("openemr")
    if not openemr_spec or not openemr_id:
        return

    path_id = _patient_path(patient_id, openemr_spec["id_style"])
    body = _format_body(openemr_spec, row)
    if extra_fields:
        body.update(extra_fields)
    body["enddate"] = _format_date(openemr_spec, "enddate", end_date)
    resp = requests.put(
        f"{_config()['apiUrl']}/patient/{path_id}/{openemr_spec['list_type']}/{openemr_id}",
        json=body,
        headers=_headers(),
    )
    resp.raise_for_status()
