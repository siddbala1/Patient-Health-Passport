export default function PatientCard({ patient, source }) {
  return (
    <div className="patient-card">
      <div className="patient-card__header">
        <h2>{patient.name}</h2>
        <span className="badge">{source}</span>
      </div>
      <div className="patient-card__grid">
        <Detail label="Date of Birth" value={patient.birthDate} />
        <Detail label="Gender" value={patient.gender} />
        <Detail label="Location" value={[patient.city, patient.state].filter(Boolean).join(', ')} />
        <Detail label="Phone" value={patient.phone} />
      </div>
    </div>
  );
}

function Detail({ label, value }) {
  return (
    <div className="detail">
      <span className="detail__label">{label}</span>
      <span className="detail__value">{value || '—'}</span>
    </div>
  );
}
