# Write functions for Store 1. These take the normalizer's output and
# persist it per patient_id, following the append-only versioning rule for
# clinical tables: an edited/replaced row is never deleted or overwritten,
# it's marked ended_at and a new row is appended in its place.

import json
from datetime import datetime, timezone
from storage.db import get_connection
from storage.resources import RESOURCES

# Matching an incoming clinical entry against a patient's current
# (ended_at IS NULL) rows uses each resource's "key" fields as its natural
# identity (see storage/resources.py). If the identity matches but the
# "values" fields differ, the row is versioned. If identity and values both
# match, nothing happens (avoids duplicate rows on every re-sync). If the
# identity doesn't match anything, it's a plain insert.
#
# Observations are dated facts, not a single evolving thing per name, so
# their key includes the date: a new date is always a new row, and only a
# same-name-same-date re-read with a changed value versions the existing one.
#
# For resources with an "openemr" block (conditions, medications), name-only
# matching has a real failure mode: OpenEMR's own FHIR mapping doesn't always
# carry a resource's name back out (e.g. a Condition with no diagnosis code
# reads back with no code.text/coding.display at all — see normalizer.py's
# lookup_icd10_code), so normalize_conditions() falls back to "Unknown
# condition". Matched purely by name, that repull looks like a brand-new,
# unrelated condition — it ends the correctly-named row and replaces it with
# a wrong one. So when the incoming item carries an "openemr_id" (the FHIR
# resource's own id), that takes priority over name matching: it's a much
# stronger signal that this is the same underlying OpenEMR record, even if
# its display fields came back empty or different this time.


def _sync_versioned(cursor, table, patient_id, incoming, spec):
    if not incoming:
        return

    key_fields = spec["key"]
    value_fields = spec["values"]
    fields = key_fields + value_fields
    has_openemr_id = "openemr" in spec

    # For openemr-linked resources, pull every row (not just active ones),
    # so a row a user deliberately ended (e.g. via the UI's "remove") is
    # still recognized on the next passive resync. Some OpenEMR FHIR
    # endpoints (Condition, confirmed by testing) keep returning
    # resolved/ended records forever, with no way to filter them out — read
    # without this, that record looks brand-new on every login and gets
    # reinserted as an active row each time, resurrecting it forever.
    select_cols = ["id"] + fields + (["openemr_id", "ended_at"] if has_openemr_id else [])
    where_ended = "" if has_openemr_id else "AND ended_at IS NULL "
    cursor.execute(
        f"SELECT {', '.join(select_cols)} FROM {table} WHERE patient_id = %s {where_ended}ORDER BY id",
        (patient_id,),
    )
    by_key = {}
    by_openemr_id = {}
    for row in cursor.fetchall():
        row_id = row[0]
        key = tuple(row[1:1 + len(key_fields)])
        values = tuple(row[1 + len(key_fields):1 + len(fields)])
        if has_openemr_id:
            openemr_id, ended_at = row[1 + len(fields)], row[2 + len(fields)]
            is_active = ended_at is None
            if is_active:
                by_key[key] = (row_id, values)
            if openemr_id:
                # Rows are visited in id order, so the last write per
                # openemr_id here is always its most recent known state.
                by_openemr_id[openemr_id] = (row_id, key, values, is_active)
        else:
            by_key[key] = (row_id, values)

    insert_cols = ["patient_id"] + fields + (["openemr_id"] if has_openemr_id else [])
    insert_placeholders = ", ".join(["%s"] * len(insert_cols))

    for item in incoming:
        key = tuple(item.get(f) for f in key_fields)
        values = tuple(item.get(f) for f in value_fields)
        incoming_openemr_id = item.get("openemr_id") if has_openemr_id else None

        match = by_openemr_id.get(incoming_openemr_id) if incoming_openemr_id else None
        if match:
            row_id, existing_key, existing_values, is_active = match
            if not is_active:
                # Already ended locally on purpose — never resurrect it just
                # because OpenEMR's read still surfaces the old record.
                continue
            # OpenEMR drops fields on read that it never serializes — notably
            # Condition onset: its FhirConditionService uses begdate only for
            # active/inactive and never emits onsetDateTime/Period/String, so
            # onset always reads back as None. A None from the read therefore
            # means "OpenEMR didn't send this", not "the value was cleared".
            # Coalesce incoming over what's stored so a dropped field keeps its
            # existing value instead of wiping a date the patient entered.
            # "local_only" fields (see resources.py) are ones OpenEMR can't
            # represent at all — e.g. it hardcodes every allergy's category
            # to "medication" — so once Store 1 has a value, a read never
            # overwrites it.
            local_only = spec.get("local_only", ())
            values = tuple(
                ev if (f in local_only and ev is not None)
                else (v if v is not None else ev)
                for f, v, ev in zip(value_fields, values, existing_values)
            )
            if existing_key == key and existing_values == values:
                continue  # identical to what's already stored, nothing to do
        else:
            match = by_key.get(key)
            row_id = match[0] if match else None
            if match and match[1] == values:
                continue

        if match:
            cursor.execute(
                f"UPDATE {table} SET ended_at = %s WHERE id = %s",
                (datetime.now(timezone.utc), row_id),
            )

        insert_values = [patient_id, *key, *values]
        if has_openemr_id:
            insert_values.append(incoming_openemr_id)
        cursor.execute(
            f"INSERT INTO {table} ({', '.join(insert_cols)}) VALUES ({insert_placeholders})",
            insert_values,
        )


def save_patient_info(patient_id, source, patient):
    """patient_info is a snapshot, not a history: updates overwrite in place."""
    if not patient:
        return
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO patient_info (patient_id, source, name, gender, birth_date, city, state, phone)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                source = VALUES(source),
                name = VALUES(name),
                gender = VALUES(gender),
                birth_date = VALUES(birth_date),
                city = VALUES(city),
                state = VALUES(state),
                phone = VALUES(phone)
            """,
            (
                patient_id,
                source,
                patient.get("name"),
                patient.get("gender"),
                patient.get("birthDate"),
                patient.get("city"),
                patient.get("state"),
                patient.get("phone"),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def save_resource(patient_id, table, items):
    """Sync one resource type's incoming rows (e.g. "conditions") for a
    patient, per the key/value fields registered in storage/resources.py."""
    spec = RESOURCES[table]
    conn = get_connection()
    try:
        cursor = conn.cursor()
        _sync_versioned(cursor, table, patient_id, items, spec)
        conn.commit()
    finally:
        conn.close()


def save_normalized_records(patient_id, clean):
    """Persist one normalize_records() output for a patient into Store 1."""
    save_patient_info(patient_id, clean.get("source"), clean.get("patient"))
    for table in RESOURCES:
        save_resource(patient_id, table, clean.get(table) or [])


def save_note_explanation(patient_id, note_id, explanation, model):
    """Store the explanation generated for one clinical_notes row. INSERT
    IGNORE: if two requests raced to generate the same note's explanation,
    the first one wins and the second is a no-op."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT IGNORE INTO note_explanations (patient_id, note_id, explanation, model) "
            "VALUES (%s, %s, %s, %s)",
            (patient_id, note_id, json.dumps(explanation), model),
        )
        conn.commit()
    finally:
        conn.close()


def _end_row(table, patient_id, row_id):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE {table} SET ended_at = %s WHERE id = %s AND patient_id = %s AND ended_at IS NULL",
            (datetime.now(timezone.utc), row_id, patient_id),
        )
        conn.commit()
    finally:
        conn.close()


# Explicit "remove via UI" hook for when a patient marks a condition
# resolved, stops a medication, or retracts an observation by hand, as
# opposed to a passive re-sync from OpenEMR. Just ends the row; the
# replacement (if any) is a normal insert through save_resource() above.
def end_resource(patient_id, table, row_id):
    _end_row(table, patient_id, row_id)


# Explicit "add via UI" hook: a patient adding a single new condition or
# medication by hand. Unlike save_resource() (which syncs a whole batch
# from a passive OpenEMR read), this always inserts exactly one row and
# hands back its id, so the caller can push it to OpenEMR and record the
# resulting openemr_id. Still respects the same key-match versioning rule:
# adding an item whose key matches an existing active row ends that row
# first, same as a re-sync would.
def add_resource(patient_id, table, item):
    spec = RESOURCES[table]
    key_fields = spec["key"]
    value_fields = spec["values"]
    fields = key_fields + value_fields

    conn = get_connection()
    try:
        cursor = conn.cursor()
        key = tuple(item.get(f) for f in key_fields)
        key_match = " AND ".join(f"{f} = %s" for f in key_fields)
        cursor.execute(
            f"SELECT id FROM {table} WHERE patient_id = %s AND ended_at IS NULL AND {key_match}",
            (patient_id, *key),
        )
        existing = cursor.fetchone()
        if existing:
            cursor.execute(
                f"UPDATE {table} SET ended_at = %s WHERE id = %s",
                (datetime.now(timezone.utc), existing[0]),
            )

        insert_cols = ", ".join(["patient_id"] + fields)
        insert_placeholders = ", ".join(["%s"] * (len(fields) + 1))
        values = tuple(item.get(f) for f in fields)
        cursor.execute(
            f"INSERT INTO {table} ({insert_cols}) VALUES ({insert_placeholders})",
            (patient_id, *values),
        )
        new_id = cursor.lastrowid
        conn.commit()
        return new_id
    finally:
        conn.close()


def set_openemr_id(table, row_id, openemr_id):
    """Record the id OpenEMR assigned a row this app just pushed to it, so a
    later edit/remove of that row can address the right OpenEMR record."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE {table} SET openemr_id = %s WHERE id = %s", (openemr_id, row_id)
        )
        conn.commit()
    finally:
        conn.close()
