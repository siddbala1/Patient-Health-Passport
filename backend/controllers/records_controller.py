# Patient-initiated writes: add/edit/remove a condition or medication from
# the UI. Every write hits Store 1 first (the app's source of truth), then
# best-effort mirrors it to OpenEMR via storage/openemr_write.py. A failed
# OpenEMR push never rolls back or blocks the Store 1 write — it's reported
# back to the caller via "synced_to_openemr" so the UI can flag it, but the
# patient's edit still takes effect locally either way.
#
# Only resource types with an "openemr" block in storage/resources.py are
# writable here (currently conditions and medications) — observations have
# no push target yet, so they're rejected with a 400 rather than silently
# accepted and never synced.

from datetime import datetime, timezone
from flask import request, jsonify

from controllers.auth_controller import get_session_patient_id
from storage import store, queries
from storage.resources import RESOURCES
from storage.openemr_write import push_create, push_end

WRITABLE_TABLES = {table for table, spec in RESOURCES.items() if "openemr" in spec}


def _require_session_and_table(session_id, table):
    if table not in WRITABLE_TABLES:
        return None, (jsonify({"error": f"'{table}' can't be edited here"}), 400)
    patient_id = get_session_patient_id(session_id)
    if not patient_id:
        return None, (jsonify({"error": "Session not found or expired"}), 404)
    return patient_id, None


def _extra_fields(table, row):
    """Request-body fields that don't map 1:1 from a Store 1 column.

    Conditions: OpenEMR's FHIR Condition mapping never carries the free-text
    title, only a coded "diagnosis" — so every condition write carries the
    clinician-entered ICD-10 code straight through as OpenEMR's "diagnosis"
    field, instead of coming back as "Unknown condition" on a later re-pull.
    The UI requires this field, so it's always present here.

    Allergies: OpenEMR derives an allergy's status from its end date (no end
    date -> active), and its write endpoint accepts no status field. So an
    allergy the patient saves as inactive is pushed with an end date of
    today; otherwise OpenEMR would read it back as active and the next login
    would revert it. ("resolved" can't round-trip — it needs OpenEMR's
    "outcome" flag, which the endpoint doesn't accept — so the UI only
    offers active/inactive.)"""
    if table == "conditions":
        code = row.get("icd10")
        return {"diagnosis": f"ICD10:{code}"} if code else None
    if table == "allergies" and row.get("status") in ("inactive", "resolved"):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return {"enddate": f"{today} 00:00:00"}
    return None


def _push_create_safe(patient_id, table, row):
    try:
        return push_create(patient_id, RESOURCES[table], row, extra_fields=_extra_fields(table, row)), True
    except Exception as e:
        print(f"OpenEMR push_create failed for {table}: {e}")
        return None, False


def _push_end_safe(patient_id, table, openemr_id, row, end_date):
    if not openemr_id:
        return False
    try:
        push_end(patient_id, RESOURCES[table], openemr_id, row, end_date, extra_fields=_extra_fields(table, row))
        return True
    except Exception as e:
        print(f"OpenEMR push_end failed for {table}: {e}")
        return False


def add_record(session_id, table):
    """Patient adds a brand-new condition/medication."""
    patient_id, error = _require_session_and_table(session_id, table)
    if error:
        return error

    item = request.get_json(force=True, silent=True) or {}
    spec = RESOURCES[table]
    required = spec["key"] + spec["values"]
    missing = [f for f in required if not item.get(f)]
    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400
    item = {f: item[f] for f in required}

    row_id = store.add_resource(patient_id, table, item)
    openemr_id, synced = _push_create_safe(patient_id, table, item)
    if openemr_id:
        store.set_openemr_id(table, row_id, openemr_id)

    return jsonify({"id": row_id, "synced_to_openemr": synced, **item}), 201


def edit_record(session_id, table, row_id):
    """Patient edits a condition/medication. Implemented as end-old +
    insert-new, matching Store 1's append-only versioning everywhere else."""
    patient_id, error = _require_session_and_table(session_id, table)
    if error:
        return error

    current = queries.get_resource_row(patient_id, table, row_id)
    if not current:
        return jsonify({"error": "Record not found"}), 404

    spec = RESOURCES[table]
    changes = request.get_json(force=True, silent=True) or {}
    fields = spec["key"] + spec["values"]
    updated = {f: changes.get(f, current.get(f)) for f in fields}

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    store.end_resource(patient_id, table, row_id)
    _push_end_safe(patient_id, table, current.get("openemr_id"), current, today)

    new_row_id = store.add_resource(patient_id, table, updated)
    openemr_id, synced = _push_create_safe(patient_id, table, updated)
    if openemr_id:
        store.set_openemr_id(table, new_row_id, openemr_id)

    return jsonify({"id": new_row_id, "synced_to_openemr": synced, **updated})


def remove_record(session_id, table, row_id):
    """Patient removes (ends) a condition/medication. Never a hard delete,
    in Store 1 or in OpenEMR — just marks it ended, same as elsewhere."""
    patient_id, error = _require_session_and_table(session_id, table)
    if error:
        return error

    current = queries.get_resource_row(patient_id, table, row_id)
    if not current:
        return jsonify({"error": "Record not found"}), 404

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    store.end_resource(patient_id, table, row_id)
    synced = _push_end_safe(patient_id, table, current.get("openemr_id"), current, today)

    return jsonify({"id": row_id, "synced_to_openemr": synced})
