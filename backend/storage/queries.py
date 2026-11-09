# Read functions for Store 1. These are what the backend/UI calls to get a
# patient's current data — the app's source of truth, not a live OpenEMR read.


##Creation of Patient ID for ease of querying de-identified patient-specific data across multiple tables pertaining to different FHIR resources.

from storage.db import get_connection
from storage.resources import RESOURCES


def get_patient_info(patient_id):
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT patient_id, source, name, gender, birth_date, city, state, phone "
            "FROM patient_info WHERE patient_id = %s",
            (patient_id,),
        )
        return cursor.fetchone()
    finally:
        conn.close()


def _get_active_rows(table, patient_id, columns):
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        col_list = ", ".join(columns)
        cursor.execute(
            f"SELECT {col_list} FROM {table} WHERE patient_id = %s AND ended_at IS NULL "
            f"ORDER BY created_at DESC",
            (patient_id,),
        )
        return cursor.fetchall()
    finally:
        conn.close()


def get_resource(patient_id, table):
    spec = RESOURCES[table]
    columns = ["id"] + spec["key"] + spec["values"]
    return _get_active_rows(table, patient_id, columns)


def get_resource_row(patient_id, table, row_id):
    """A single row (any table registered in RESOURCES), including
    openemr_id — used by the write endpoints to push edits/removals back
    to OpenEMR without needing a second, separate lookup."""
    spec = RESOURCES[table]
    columns = ["id"] + spec["key"] + spec["values"] + ["openemr_id"]
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        col_list = ", ".join(columns)
        cursor.execute(
            f"SELECT {col_list} FROM {table} WHERE id = %s AND patient_id = %s AND ended_at IS NULL",
            (row_id, patient_id),
        )
        return cursor.fetchone()
    finally:
        conn.close()


def get_notes_with_explanations(patient_id):
    """A patient's current clinical notes, newest first, each with its stored
    explanation (None if not generated yet). Includes the raw note_text for
    backend use only — callers must never return it to the frontend."""
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT n.id, n.title, n.note_date, n.note_text, e.explanation "
            "FROM clinical_notes n "
            "LEFT JOIN note_explanations e ON e.note_id = n.id "
            "WHERE n.patient_id = %s AND n.ended_at IS NULL "
            "ORDER BY n.note_date DESC, n.id DESC",
            (patient_id,),
        )
        return cursor.fetchall()
    finally:
        conn.close()


def get_patient_record(patient_id):
    """Assemble a patient's current record from Store 1, shaped like
    normalize_records()'s output so the UI doesn't need to change."""
    info = get_patient_info(patient_id)
    if info is None:
        return None
    record = {
        "source": info["source"],
        "patientId": patient_id,
        "patient": {
            "name": info["name"],
            "gender": info["gender"],
            "birthDate": info["birth_date"],
            "city": info["city"],
            "state": info["state"],
            "phone": info["phone"],
        },
    }
    for table, spec in RESOURCES.items():
        if spec.get("internal"):
            continue  # stored for backend use only (e.g. raw clinical notes)
        record[table] = get_resource(patient_id, table)
    return record
