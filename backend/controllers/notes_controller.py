# Plain-language views of a patient's clinical notes. The raw note text stays
# in Store 1 (clinical_notes) and is only ever sent to the explainer model —
# this endpoint returns the explanation, never the note itself.
#
# Explanations are generated lazily the first time a note is viewed, then
# stored (note_explanations), so each note version costs one model call.

import json

from flask import jsonify

from controllers.auth_controller import get_session_patient_id
from llm import note_explainer
from storage import queries, store


def _record_context(patient_id):
    return {
        table: [row["name"] for row in queries.get_resource(patient_id, table)]
        for table in ("conditions", "medications", "allergies")
    }


def _present(row, explanation, status):
    out = {"id": row["id"], "title": row["title"], "date": row["note_date"], "status": status}
    if explanation:
        out.update(
            summary=explanation["summary"],
            terms=explanation["terms"],
            next_steps=explanation["next_steps"],
        )
    return out


def get_notes(session_id):
    patient_id = get_session_patient_id(session_id)
    if not patient_id:
        return jsonify({"error": "Session not found or expired"}), 404

    rows = queries.get_notes_with_explanations(patient_id)
    context = None  # only fetched if something needs generating
    results = []

    for row in rows:
        if row["explanation"]:
            results.append(_present(row, json.loads(row["explanation"]), "ready"))
            continue

        if not note_explainer.is_configured():
            results.append(_present(row, None, "not_configured"))
            continue

        if context is None:
            context = _record_context(patient_id)
        try:
            explanation = note_explainer.explain_note(row["note_text"], context)
        except note_explainer.ExplainerNotConfigured:
            results.append(_present(row, None, "not_configured"))
            continue
        except note_explainer.ExplainerFailed as e:
            print(f"Note explanation failed for note {row['id']}: {e}")
            results.append(_present(row, None, "unavailable"))
            continue

        unmatched = note_explainer.check_numbers(row["note_text"], explanation)
        if unmatched:
            # A number in the explanation that isn't in the note could be a
            # wrong dose or vital sign. Hide it, don't store it, retry next view.
            print(f"Note {row['id']} explanation hidden: numbers not in note: {unmatched}")
            results.append(_present(row, None, "needs_review"))
            continue

        store.save_note_explanation(patient_id, row["id"], explanation, note_explainer.MODEL)
        results.append(_present(row, explanation, "ready"))

    return jsonify({"notes": results})
