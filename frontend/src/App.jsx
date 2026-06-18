import { useState, useEffect } from 'react';
import { fetchPatient, fetchSession, getSmartConnectUrl } from './api';
import logo from './assets/logo.avif';
import PatientCard from './components/PatientCard';
import ResourceTable from './components/ResourceTable';
import Tabs from './components/Tabs';
import './App.css';

const CONDITION_COLS = [
  { key: 'name', label: 'Condition' },
  { key: 'status', label: 'Status' },
  { key: 'onset', label: 'Onset' },
  { key: 'source', label: 'Source' },
];

const MEDICATION_COLS = [
  { key: 'name', label: 'Medication' },
  { key: 'status', label: 'Status' },
  { key: 'date', label: 'Date' },
  { key: 'source', label: 'Source' },
];

const OBSERVATION_COLS = [
  { key: 'name', label: 'Observation' },
  { key: 'value', label: 'Value' },
  { key: 'date', label: 'Date' },
  { key: 'source', label: 'Source' },
];

function tagRows(rows, source) {
  return (rows || []).map((r) => ({ ...r, source }));
}

export default function App() {
  const [query, setQuery] = useState('');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // On load, check if we were redirected back from SMART OAuth
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const sessionId = params.get('session');
    if (!sessionId) return;

    // Clean the URL immediately
    window.history.replaceState({}, '', window.location.pathname);

    setLoading(true);
    fetchSession(sessionId)
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  async function handleSearch(e) {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    setData(null);
    try {
      const result = await fetchPatient(query.trim());
      setData(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  const conditions = data ? tagRows(data.conditions, data.source) : [];
  const medications = data ? tagRows(data.medications, data.source) : [];
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
        <ResourceTable
          columns={CONDITION_COLS}
          rows={conditions}
          emptyMessage="No conditions on record."
        />
      ),
    },
    {
      label: 'Medications',
      count: medications.length,
      content: (
        <ResourceTable
          columns={MEDICATION_COLS}
          rows={medications}
          emptyMessage="No medications on record."
        />
      ),
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
          <form className="search-form" onSubmit={handleSearch}>
            <input
              className="search-form__input"
              type="text"
              placeholder="Enter patient name (e.g. Walton)"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              disabled={loading}
            />
            <button className="search-form__btn" type="submit" disabled={loading}>
              {loading ? 'Searching…' : 'Search'}
            </button>
          </form>
          <a className="smart-btn" href={getSmartConnectUrl()}>
            Connect via SMART
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
            <p>Search for a patient to view their health records.</p>
          </div>
        )}
      </main>
    </div>
  );
}
