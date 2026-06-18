# Manual Normalizer for messy FHIR bundles
# Takes raw FHIR bundles and flattens them into clean, 
# consistent objects the frontend can render directly.
# This protects the frontend from FHIR's structural quirks
# and from differences between data sources.


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


def normalize_conditions(bundle):
    """Flatten a FHIR Condition bundle into a list of clean conditions."""
    results = []
    for entry in bundle.get("entry", []) if bundle else []:
        resource = entry.get("resource", {})
        results.append({
            "name": _safe_get(resource, "code", "text", default="Unknown condition"),
            "status": _safe_get(resource, "clinicalStatus", "coding", 0, "code", default="—"),
            "onset": resource.get("onsetDateTime", "—")[:10] if resource.get("onsetDateTime") else "—",
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
    }
#Last function allows an easier transition to using AI 
# for more hospital-hospital normalization in the future, by providing a single clean structure f
#or the AI to work with.