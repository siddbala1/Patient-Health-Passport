# Manual Normalizer for messy FHIR bundles
# Takes raw FHIR bundles and flattens them into clean, 
# consistent objects the frontend can render directly.
# This protects the frontend from FHIR's structural quirks
# and from differences between data sources.

import base64
import re
import requests

_TAG_RE = re.compile(r"<[^>]+>")
_DATA_ABSENT_REASON_SYSTEM = "http://terminology.hl7.org/CodeSystem/data-absent-reason"


def _narrative_text(resource):
    """Extract plain text from a FHIR Narrative (resource.text.div), which is
    XHTML-wrapped, e.g. "<div xmlns='...'>Peanuts</div>"."""
    div = _safe_get(resource, "text", "div")
    if not div:
        return None
    return _TAG_RE.sub("", div).strip() or None


def _safe_get(d, *keys, default=None):
    """Safely dig into nested dicts/lists without crashing on missing keys."""
    current = d
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
        elif isinstance(current, list) and isinstance(key, int):
            current = current[key] if len(current) > key else None
        else:
            return default
        if current is None:
            return default
    return current


def normalize_patient(patient):
    """Flatten a FHIR Patient resource into clean demographics."""
    if not patient:
        return None

    name = _safe_get(patient, "name", 0, default={})
    given = name.get("given", []) if name else []
    family = name.get("family", "") if name else ""
    full_name = f"{' '.join(given)} {family}".strip()
#Safely retrieves a patients name, last name, family name, and full name from a bundle 
    address = _safe_get(patient, "address", 0, default={})

    return {
        "name": full_name or "Unknown",
        "gender": patient.get("gender", "—"),
        "birthDate": patient.get("birthDate", "—"),
        "city": address.get("city", "—") if address else "—",
        "state": address.get("state", "—") if address else "—",
        "phone": _safe_get(patient, "telecom", 0, "value", default="—"),
    }
#Same principle applies to these normalization functions



# Simple in-memory cache so repeated codes don't re-hit the API
_icd10_cache = {}

def lookup_icd10_name(code):
    """Resolve an ICD-10 code to its official name via NIH's free API.
    Returns the code itself if lookup fails, so nothing ever breaks."""
    if not code:
        return None
    if code in _icd10_cache:
        return _icd10_cache[code]
    try:
        resp = requests.get(
            "https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search",
            params={"sf": "code", "terms": code, "df": "code,name"},
            timeout=5,
        )
        data = resp.json()
        # Response format: [total, [codes], null, [[code, name], ...]]
        rows = data[3] if len(data) > 3 else []
        for row in rows:
            if row[0].upper() == code.upper():
                name = row[1]
                _icd10_cache[code] = name
                return name
    except Exception as e:
        print(f"ICD-10 lookup failed for {code}: {e}")
    _icd10_cache[code] = code  # cache the miss as the raw code
    return code
##CODE ABOVE ADDRESSES ISSUES WITH MISSING DISPLAY TEXT IN FHIR CONDITIONS BY LOOKING UP THE CODE IN AN EXTERNAL API


def normalize_conditions(bundle):
    """Flatten FHIR Conditions. Resolves codes to names when display text is missing."""
    results = []
    for entry in bundle.get("entry", []) if bundle else []:
        resource = entry.get("resource", {})
        coding = _safe_get(resource, "code", "coding", 0, default={})
        code_val = coding.get("code", "")
        # Unlike AllergyIntolerance, OpenEMR's Condition FHIR mapping has no
        # narrative fallback: FhirConditionService::populateCode() simply
        # never calls setCode() when there's no diagnosis, and nothing else
        # in that service carries the free-text title either (confirmed
        # against OpenEMR's source — no setText()/narrative call exists in
        # FhirConditionService.php at all). So when a condition has no ICD-10
        # code, its name is genuinely unrecoverable over FHIR, not just
        # hard-to-find — the fallback below says so explicitly rather than
        # displaying a bare "Unknown condition" that looks like an app bug.
        code_val_present = bool(code_val)
        name = (_safe_get(resource, "code", "text")
                or (coding.get("display") or "").strip()
                or lookup_icd10_name(code_val)
                or ("Unknown condition (no ICD-10 code)" if not code_val_present else "Unknown condition"))
        # Onset: OpenEMR's FHIR Condition mapping never emits an onset field
        # at all (confirmed against FhirConditionService.php — begdate is
        # used only to compute active/inactive clinicalStatus, never mapped
        # to onsetDateTime/onsetPeriod/onsetString). These three reads exist
        # for sources that do send onset; store None (→ clean SQL NULL) when
        # truly absent, never the "—" display placeholder, which must never
        # be persisted as data.
        onset_raw = (resource.get("onsetDateTime")
                     or _safe_get(resource, "onsetPeriod", "start")
                     or resource.get("onsetString"))
        results.append({
            "name": name,
            "status": _safe_get(resource, "clinicalStatus", "coding", 0, "code", default="—"),
            "onset": onset_raw[:10] if onset_raw else None,
            # The ICD-10 code itself, straight from the coding entry — kept
            # separate from "name" so a repull doesn't lose the code a
            # clinician entered even on the rare bundle where the display
            # text came back empty and name fell through to lookup/"Unknown".
            "icd10": code_val or None,
            # OpenEMR's own record id (== lists.uuid), when this bundle came
            # from OpenEMR — lets store.py recognize a repull of a condition
            # it previously pushed even if the name/code round-tripped badly,
            # instead of key-matching purely on name (see _sync_versioned).
            "openemr_id": resource.get("id"),
        })
    return results


def normalize_medications(bundle):
    """Flatten a FHIR MedicationRequest bundle into clean medications.
    Handles BOTH medicationCodeableConcept (inline name) and
    medicationReference (a pointer with no name)."""
    results = []
    for entry in bundle.get("entry", []) if bundle else []:
        resource = entry.get("resource", {})

        # Quirk: medication name can live in two different places
        name = _safe_get(resource, "medicationCodeableConcept", "text")
        if not name:
            # Falls back to the reference display if present
            name = _safe_get(resource, "medicationReference", "display", default="Medication (referenced)")

        results.append({
            "name": name,
            "status": resource.get("status", "—"),
            "date": resource.get("authoredOn", "—")[:10] if resource.get("authoredOn") else "—",
        })
    return results


def normalize_observations(bundle):
    """Flatten a FHIR Observation bundle into clean observations.
    Handles BOTH valueQuantity (single value) and component
    (multi-part, e.g. blood pressure with systolic + diastolic)."""
    results = []
    for entry in bundle.get("entry", []) if bundle else []:
        resource = entry.get("resource", {})
        name = _safe_get(resource, "code", "text", default="Observation")
        date = resource.get("effectiveDateTime", "—")
        date = date[:10] if date and date != "—" else "—"
        category = _safe_get(resource, "category", 0, "coding", 0, "code", default="other")

        # Quirk: value can be a single quantity OR split into components
        if "valueQuantity" in resource:
            q = resource["valueQuantity"]
            value = f"{q.get('value', '')} {q.get('unit', '')}".strip()
        elif "component" in resource:
            parts = []
            for comp in resource["component"]:
                comp_name = _safe_get(comp, "code", "text", default="")
                q = comp.get("valueQuantity", {})
                parts.append(f"{comp_name}: {q.get('value', '')} {q.get('unit', '')}".strip())
            value = " / ".join(parts)
        elif "valueCodeableConcept" in resource:
            value = _safe_get(resource, "valueCodeableConcept", "text", default="—")
        else:
            value = "—"

        results.append({
            "name": name,
            "value": value,
            "date": date,
            "category": category,
        })
    return results


def normalize_allergies(bundle):
    """Flatten a FHIR AllergyIntolerance bundle. When an allergy has no ICD
    diagnosis code (e.g. one added through this app, which only ever writes
    a free-text title), OpenEMR's FHIR mapping sets code.coding to a FHIR
    "data absent reason" placeholder — code "unknown", display "Unknown" —
    rather than leaving it empty (see
    FhirAllergyIntoleranceService::parseOpenEMRRecord). Read naively, that
    placeholder looks like real data and the allergen shows as literally
    "Unknown". OpenEMR does still preserve the free-text title, but in the
    resource's narrative (text.div) rather than code.text, so that placeholder
    is detected and skipped in favor of the narrative before falling back to
    the generic "Unknown allergy"."""
    results = []
    for entry in bundle.get("entry", []) if bundle else []:
        resource = entry.get("resource", {})
        coding = _safe_get(resource, "code", "coding", 0, default={})
        is_data_absent = coding.get("system") == _DATA_ABSENT_REASON_SYSTEM
        name = (_safe_get(resource, "code", "text")
                or (not is_data_absent and (coding.get("display") or "").strip())
                or _narrative_text(resource)
                or "Unknown allergy")
        # category is a FHIR list (e.g. ["medication"]); take the first.
        # None, never the "—" display placeholder, when a field is absent:
        # a persisted "—" is garbage data (it saved as mojibake) and, being
        # non-None, defeats store.py's keep-existing-on-missing coalesce.
        category = _safe_get(resource, "category", 0)
        results.append({
            "name": name,
            "status": _safe_get(resource, "clinicalStatus", "coding", 0, "code"),
            "category": category,
            "criticality": resource.get("criticality"),
            # Captured for a future write-back path (see resources.py); unused
            # while allergies stay read-only.
            "openemr_id": resource.get("id"),
        })
    return results


def normalize_immunizations(bundle):
    """Flatten a FHIR Immunization bundle. Read-only: OpenEMR's Standard API
    exposes no immunization write endpoint (confirmed 404), so these only
    ever flow OpenEMR → Passport."""
    results = []
    for entry in bundle.get("entry", []) if bundle else []:
        resource = entry.get("resource", {})
        coding = _safe_get(resource, "vaccineCode", "coding", 0, default={})
        name = (_safe_get(resource, "vaccineCode", "text")
                or (coding.get("display") or "").strip()
                or "Unknown vaccine")
        date = resource.get("occurrenceDateTime") or resource.get("occurrenceString")
        results.append({
            "name": name,
            "status": resource.get("status", "—"),
            "date": date[:10] if date else None,
            "openemr_id": resource.get("id"),
        })
    return results


def normalize_clinical_notes(bundle):
    """Flatten a FHIR DocumentReference bundle of clinical notes into raw
    note rows for Store 1. OpenEMR delivers the text inline as a base64
    text/plain attachment (content[].attachment.data); anything else (PDFs,
    URL-only attachments) is skipped for now rather than stored half-read."""
    results = []
    for entry in bundle.get("entry", []) if bundle else []:
        resource = entry.get("resource", {})
        if resource.get("resourceType") != "DocumentReference":
            continue  # e.g. an OperationOutcome entry
        if resource.get("status") not in (None, "current"):
            continue

        text = None
        for content in resource.get("content", []):
            attachment = content.get("attachment", {})
            data = attachment.get("data")
            if not data:
                continue
            try:
                decoded = base64.b64decode(data).decode("utf-8", errors="replace")
            except Exception:
                continue
            ctype = attachment.get("contentType", "")
            if ctype.startswith("text/html"):
                decoded = _TAG_RE.sub("", decoded)
            elif not ctype.startswith("text/"):
                continue
            text = decoded.strip() or None
            if text:
                break
        if not text:
            continue

        coding = _safe_get(resource, "type", "coding", 0, default={})
        title = (_safe_get(resource, "type", "text")
                 or (coding.get("display") or "").strip()
                 or "Clinical note")
        date = resource.get("date")
        results.append({
            "doc_id": resource.get("id"),
            "title": title,
            "note_date": date[:10] if date else None,
            "note_type": coding.get("code"),
            "note_text": text,
        })
    return results


def normalize_procedures(bundle):
    """Flatten a FHIR Procedure bundle. Read-only, same reason as
    immunizations (Standard API returns 404 for procedure writes)."""
    results = []
    for entry in bundle.get("entry", []) if bundle else []:
        resource = entry.get("resource", {})
        coding = _safe_get(resource, "code", "coding", 0, default={})
        name = (_safe_get(resource, "code", "text")
                or (coding.get("display") or "").strip()
                or "Unknown procedure")
        # Procedure timing is either a single dateTime or a period.
        date = (resource.get("performedDateTime")
                or _safe_get(resource, "performedPeriod", "start"))
        results.append({
            "name": name,
            "status": resource.get("status", "—"),
            "date": date[:10] if date else None,
            "openemr_id": resource.get("id"),
        })
    return results


def normalize_records(raw):
    """Top-level: take the full raw records object from a source
    and return a clean, frontend-ready structure."""
    records = raw.get("records", {})

    return {
        "source": raw.get("source", "Unknown source"),
        "patientId": raw.get("patientId", "—"),
        "patient": normalize_patient(records.get("patient")),
        "conditions": normalize_conditions(records.get("conditions")),
        "medications": normalize_medications(records.get("medications")),
        "observations": normalize_observations(records.get("observations")),
        "allergies": normalize_allergies(records.get("allergies")),
        "immunizations": normalize_immunizations(records.get("immunizations")),
        "procedures": normalize_procedures(records.get("procedures")),
        "clinical_notes": normalize_clinical_notes(records.get("documents")),
    }
#Last function allows an easier transition to using AI 
# for more hospital-hospital normalization in the future, by providing a single clean structure 
#for the AI to work with.