const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:3000';

export async function fetchPatient(name) {
  const res = await fetch(`${BASE_URL}/local-clean?name=${encodeURIComponent(name)}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || `Server error ${res.status}`);
  }
  return res.json();
}

export async function fetchSession(sessionId) {
  const res = await fetch(`${BASE_URL}/session/${sessionId}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || `Session error ${res.status}`);
  }
  return res.json();
}

export function getSmartConnectUrl() {
  return `${BASE_URL}/connect?source=sandbox`;
}

//Exports created functions to be used 
// in files like app.js and other components that
// need to make API calls.  If the link changes, 
// it can be updated here and all components will use
//  the new link.
