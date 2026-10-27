# Registry of Store 1's versioned clinical resource tables. store.py and
# queries.py both drive off this instead of hardcoding a function per
# resource, so adding a new FHIR resource type only takes:
#   1. A table in init.sql: id, patient_id, <key + value columns>,
#      openemr_id, created_at, ended_at (same shape as conditions/
#      medications/observations).
#   2. An entry here, matching the normalizer's output key for that resource.
#   3. A normalize_<resource>() function in normalizer.py, wired into
#      normalize_records()'s returned dict under the same key.
#   4. If patients should be able to push edits of this resource to OpenEMR,
#      an "openemr" block (see below); otherwise omit it and the resource
#      just stays local to Store 1 (e.g. observations, for now).
#
# "key" fields identify a natural-identity match against a patient's current
# rows (see _sync_versioned in store.py); "values" are the fields that, if
# changed, cause the old row to be ended and a new one inserted.
#
# "openemr", when present, tells storage/openemr_write.py how to mirror a
# write to OpenEMR's native Standard API (/apis/default/api), which has no
# single uniform resource-addressing scheme:
#   - list_type: the "type" value under OpenEMR's generic `lists` table
#     (what its medical_problem/medication/etc. endpoints are backed by).
#   - id_style: "uuid" if the endpoint takes Store 1's patient_id directly
#     in the URL, "pid" if it needs OpenEMR's internal numeric patient id
#     (resolved via a lookup — see _resolve_pid in openemr_write.py).
#   - fields: local field name -> OpenEMR request-body field name.
#   - datetime_fields: OpenEMR field names (from "fields"'s values) that need
#     a full "Y-m-d H:i:s" datetime rather than a plain "Y-m-d" date. This is
#     genuinely per-endpoint, not a `lists`-table-wide rule — confirmed
#     against OpenEMR's source that ConditionValidator requires plain
#     "Y-m-d" for medical_problem's begdate/enddate, while ListService
#     (medication, and any other generic-list-backed resource) requires
#     "Y-m-d H:i:s". Omit this key for endpoints that want plain dates.

RESOURCES = {
    "conditions": {
        "key": ["name"],
        "values": ["status", "onset", "icd10"],
        "openemr": {
            "list_type": "medical_problem",
            "id_style": "uuid",
            "fields": {"name": "title", "onset": "begdate"},
        },
    },
    "medications": {
        "key": ["name"],
        "values": ["status", "date"],
        "openemr": {
            "list_type": "medication",
            "id_style": "pid",
            "fields": {"name": "title", "date": "begdate"},
            "datetime_fields": {"begdate", "enddate"},
        },
    },
    "observations": {
        "key": ["name", "date"],
        "values": ["value", "category"],
        # No "openemr" block: OpenEMR's Standard API has no plain
        # patient-level observation/vitals endpoint — vitals are nested
        # under an encounter (/patient/{pid}/encounter/{eid}/vital), which
        # needs encounter creation/lookup first. Deferred until that's
        # designed; observations stay Store-1-only for now.
    },
    "allergies": {
        "key": ["name"],
        "values": ["status", "category", "criticality"],
        # FhirAllergyIntoleranceService hardcodes category to "medication"
        # for every allergy, so a read can never carry a real category —
        # Store 1's value is the only truth and must survive resyncs.
        "local_only": ["category"],
        # OpenEMR's allergy write endpoint (AllergyIntoleranceRestController)
        # only accepts title/begdate/enddate/diagnosis/comments — status,
        # category, and criticality have no OpenEMR-side equivalent, so those
        # stay Store-1-only even though the resource is otherwise writable.
        # Addressed by patient uuid, not pid (confirmed against
        # _rest_routes.inc.php's "POST /api/patient/:puuid/allergy").
        "openemr": {
            "list_type": "allergy",
            "id_style": "uuid",
            "fields": {"name": "title"},
            "datetime_fields": {"begdate", "enddate"},
        },
    },
    "immunizations": {
        "key": ["name", "date"],
        "values": ["status"],
        # Read-only, permanently: OpenEMR's Standard API returns 404 for
        # /patient/{pid}/immunization — there is no write endpoint to mirror
        # to. Flows OpenEMR → Passport only, like observations.
    },
    "procedures": {
        "key": ["name", "date"],
        "values": ["status"],
        # Read-only, permanently: same as immunizations — Standard API 404s
        # for procedure writes. One-way OpenEMR → Passport.
    },
    "clinical_notes": {
        "key": ["doc_id"],
        "values": ["title", "note_date", "note_type", "note_text"],
        # Read-only, one-way OpenEMR → Passport (FHIR DocumentReference). The
        # raw note text is an input to the plain-language explanation, not
        # something the UI shows, so get_patient_record() skips "internal"
        # tables — the frontend never receives note_text.
        "internal": True,
    },
}
