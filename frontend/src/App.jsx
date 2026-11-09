import { useState, useEffect, useCallback } from 'react';
import { fetchSession, getSmartConnectUrl } from './api';
import logo from './assets/logo.avif';
import PatientCard from './components/PatientCard';
import ResourceTable from './components/ResourceTable';
import EditableResourceTable from './components/EditableResourceTable';
import NotesPanel from './components/NotesPanel';
import Tabs from './components/Tabs';
import './App.css';

const CONDITION_COLS = [
  { key: 'name', label: 'Condition' },
  { key: 'icd10', label: 'ICD-10' },
  { key: 'status', label: 'Status' },
  { key: 'onset', label: 'Onset' },
  { key: 'source', label: 'Source' },
];

const CONDITION_FIELDS = [
  { key: 'name', label: 'Condition name', type: 'text' },
  { key: 'icd10', label: 'ICD-10 code (e.g. R19.6)', type: 'text' },
  {
    key: 'status',
    label: 'Status',
    type: 'select',
    options: ['active', 'recurrence', 'relapse', 'inactive', 'remission', 'resolved'],
  },
  { key: 'onset', label: 'Onset date', type: 'date' },
];

const MEDICATION_COLS = [
  { key: 'name', label: 'Medication' },
  { key: 'status', label: 'Status' },
  { key: 'date', label: 'Date' },
  { key: 'source', label: 'Source' },
];

const MEDICATION_FIELDS = [
  { key: 'name', label: 'Medication name', type: 'text' },
  {
    key: 'status',
    label: 'Status',
    type: 'select',
    options: ['active', 'completed', 'stopped', 'on-hold', 'cancelled'],
  },
  { key: 'date', label: 'Date', type: 'date' },
];

const OBSERVATION_COLS = [
  { key: 'name', label: 'Observation' },
  { key: 'value', label: 'Value' },
  { key: 'date', label: 'Date' },
  { key: 'source', label: 'Source' },
];

const ALLERGY_COLS = [
  { key: 'name', label: 'Allergen' },
  { key: 'status', label: 'Status' },
  { key: 'category', label: 'Category' },
  { key: 'criticality', label: 'Severity' },
  { key: 'source', label: 'Source' },
];

// Only "name" pushes to OpenEMR (its allergy endpoint has no equivalent for
// status/category/criticality — see storage/resources.py) — those three
// stay Store-1-only, but the add/edit form still needs all of them since
// they're all required "values" fields for the resource.
const ALLERGY_FIELDS = [
  { key: 'name', label: 'Allergen name', type: 'text' },
  {
    key: 'status',
    label: 'Status',
    type: 'select',
    // No "resolved": it can't round-trip through OpenEMR (see
    // _extra_fields in records_controller.py), so it would revert on login.
    options: ['active', 'inactive'],
  },
  {
    key: 'category',
    label: 'Category',
    type: 'select',
    options: ['food', 'medication', 'environment', 'biologic'],
  },
  {
    // OpenEMR's own allergy form uses its "severity_ccda" list (Unassigned/
    // Mild/.../Fatal), not FHIR AllergyIntolerance.criticality's 3-value set
    // (low/high/unable-to-assess) — matching it here so the vocabulary a
    // patient picks from here is the same one clinicians see in OpenEMR.
    // Store-1-only either way: OpenEMR's allergy write endpoint whitelists
    // only title/begdate/enddate/diagnosis/comments, so this never pushes.
    key: 'criticality',
    label: 'Severity',
    type: 'select',
    options: [
      'Unassigned',
      'Mild',
      'Mild to moderate',
      'Moderate',
      'Moderate to severe',
      'Severe',
      'Life threatening severity',
      'Fatal',
    ],
  },
];

// Read-only resources. Immunizations and procedures have no OpenEMR write
// endpoint at all.

const IMMUNIZATION_COLS = [
  { key: 'name', label: 'Vaccine' },
  { key: 'status', label: 'Status' },
  { key: 'date', label: 'Date' },
  { key: 'source', label: 'Source' },
];

const PROCEDURE_COLS = [
  { key: 'name', label: 'Procedure' },
  { key: 'status', label: 'Status' },
  { key: 'date', label: 'Date' },
  { key: 'source', label: 'Source' },
];

function tagRows(rows, source) {
  return (rows || []).map((r) => ({ ...r, source }));
}

export default function App() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  // Set once the patient arrives via SMART login (/connect → /callback).
  // Editing requires a session, since writes are pushed to OpenEMR on behalf
  // of whichever patient that session belongs to.
  const [sessionId, setSessionId] = useState(null);

  // On load, check if we were redirected back from SMART OAuth
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const id = params.get('session');
    if (!id) return;

    // Clean the URL immediately
    window.history.replaceState({}, '', window.location.pathname);

    setSessionId(id);
    setLoading(true);
    fetchSession(id)
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  // Passed to EditableResourceTable so every add/edit/remove re-pulls the
  // session record afterward, keeping the table in sync with what Store 1
  // actually persisted (and whatever id/openemr_id it assigned).
  const refresh = useCallback(async () => {
    if (!sessionId) return;
    const result = await fetchSession(sessionId);
    setData(result);
  }, [sessionId]);

  const conditions = data ? tagRows(data.conditions, data.source) : [];
  const medications = data ? tagRows(data.medications, data.source) : [];
  const allergies = data ? tagRows(data.allergies, data.source) : [];
  const immunizations = data ? tagRows(data.immunizations, data.source) : [];
  const procedures = data ? tagRows(data.procedures, data.source) : [];
  const allObs = data ? tagRows(data.observations, data.source) : [];
  const vitals = allObs.filter((o) => o.category === 'vital-signs');
  const labs = allObs.filter((o) => o.category === 'laboratory');
  const otherObs = allObs.filter(
    (o) => o.category !== 'vital-signs' && o.category !== 'laboratory'
  );

  const tabs = [
    {
      label: 'Conditions',
      count: conditions.length,
      content: (
        <EditableResourceTable
          table="conditions"
          fields={CONDITION_FIELDS}
          columns={CONDITION_COLS}
          rows={conditions}
          emptyMessage="No conditions on record."
          sessionId={sessionId}
          onChange={refresh}
        />
      ),
    },
    {
      label: 'Medications',
      count: medications.length,
      content: (
        <EditableResourceTable
          table="medications"
          fields={MEDICATION_FIELDS}
          columns={MEDICATION_COLS}
          rows={medications}
          emptyMessage="No medications on record."
          sessionId={sessionId}
          onChange={refresh}
        />
      ),
    },
    {
      label: 'Allergies',
      count: allergies.length,
      content: (
        <EditableResourceTable
          table="allergies"
          fields={ALLERGY_FIELDS}
          columns={ALLERGY_COLS}
          rows={allergies}
          emptyMessage="No allergies on record."
          sessionId={sessionId}
          onChange={refresh}
        />
      ),
    },
    {
      label: 'Immunizations',
      count: immunizations.length,
      content: (
        <ResourceTable
          columns={IMMUNIZATION_COLS}
          rows={immunizations}
          emptyMessage="No immunizations on record."
        />
      ),
    },
    {
      label: 'Procedures',
      count: procedures.length,
      content: (
        <ResourceTable
          columns={PROCEDURE_COLS}
          rows={procedures}
          emptyMessage="No procedures on record."
        />
      ),
    },
    {
      label: 'Visit Notes',
      content: <NotesPanel sessionId={sessionId} />,
    },
    {
      label: 'Vitals',
      count: vitals.length,
      content: (
        <ResourceTable
          columns={OBSERVATION_COLS}
          rows={vitals}
          emptyMessage="No vital signs on record."
        />
      ),
    },
    {
      label: 'Labs',
      count: labs.length,
      content: (
        <ResourceTable
          columns={OBSERVATION_COLS}
          rows={labs}
          emptyMessage="No lab results on record."
        />
      ),
    },
    ...(otherObs.length > 0
      ? [
          {
            label: 'Other',
            count: otherObs.length,
            content: (
              <ResourceTable
                columns={OBSERVATION_COLS}
                rows={otherObs}
                emptyMessage="No other observations on record."
              />
            ),
          },
        ]
      : []),
  ];

  return (
    <div className="app">
      <header className="app__header">
        <div className="app__header-inner">
          <div className="app__logo">
            <img src={logo} alt="Sikh Health Network" className="app__logo-icon" />
            <div>
              <h1>Patient Health Passport</h1>
              <p>Sikh Health Network</p>
            </div>
          </div>
        </div>
      </header>

      <main className="app__main">
        <div className="search-row">
          <a className="smart-btn" href={getSmartConnectUrl()}>
            Log in to OpenEMR Hospital
          </a>
        </div>

        {error && (
          <div className="alert alert--error">
            <strong>Error:</strong> {error}
          </div>
        )}

        {data && (
          <div className="results">
            <PatientCard patient={data.patient} source={data.source} />
            <section className="section">
              <h3 className="section__title">Clinical Records</h3>
              <Tabs tabs={tabs} />
            </section>
          </div>
        )}

        {!data && !loading && !error && (
          <div className="empty-state">
            <p>Log in to OpenEMR Hospital to view a patient's health records.</p>
          </div>
        )}
      </main>
    </div>
  );
}
