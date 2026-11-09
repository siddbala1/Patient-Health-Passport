const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:3000';

// fetchPatient() (unauthenticated name search against a local HAPI FHIR
// server, via GET /local-clean) was removed — this app now only maintains
// OpenEMR Hospital patients, reached via the SMART login flow below.
// Restore from git history if HAPI FHIR support is needed again.

export async function fetchSession(sessionId) {
  const res = await fetch(`${BASE_URL}/session/${sessionId}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || `Session error ${res.status}`);
  }
  return res.json();
}

// Plain-language explanations of the patient's clinical notes. The server
// generates each one on first view (a few seconds), then serves it from
// Store 1; the raw note text is never sent to the browser.
export async function fetchNotes(sessionId) {
  const res = await fetch(`${BASE_URL}/session/${sessionId}/notes`);
  const payload = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(payload.error || `Notes error ${res.status}`);
  }
  return payload.notes;
}

export function getSmartConnectUrl() {
  return `${BASE_URL}/connect?source=openemr_hospital`;
}

async function writeRequest(method, path, body) {
  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body != null ? JSON.stringify(body) : undefined,
  });
  const payload = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(payload.error || `Server error ${res.status}`);
  }
  return payload;
}

export function addResource(sessionId, table, item) {
  return writeRequest('POST', `/session/${sessionId}/${table}`, item);
}

export function editResource(sessionId, table, rowId, changes) {
  return writeRequest('PUT', `/session/${sessionId}/${table}/${rowId}`, changes);
}

export function removeResource(sessionId, table, rowId) {
  return writeRequest('DELETE', `/session/${sessionId}/${table}/${rowId}`);
}

//Exports created functions to be used 
// in files like app.js and other components that
// need to make API calls.  If the link changes, 
// it can be updated here and all components will use
//  the new link.
