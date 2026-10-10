import { useState } from 'react';
import { addResource, editResource, removeResource } from '../api';

function emptyForm(fields) {
  return Object.fromEntries(fields.map((f) => [f.key, '']));
}

function Field({ field, value, onChange, disabled }) {
  if (field.type === 'select') {
    return (
      <select value={value} onChange={(e) => onChange(e.target.value)} disabled={disabled}>
        <option value="" disabled>
          Select…
        </option>
        {field.options.map((opt) => (
          <option key={opt} value={opt}>
            {opt}
          </option>
        ))}
      </select>
    );
  }
  return (
    <input
      type={field.type === 'date' ? 'date' : 'text'}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      disabled={disabled}
      placeholder={field.label}
    />
  );
}

// Conditions/medications table with inline add, edit, and remove — the only
// two resource types storage/resources.py knows how to push to OpenEMR.
// Every write goes to Store 1 first; onChange() re-pulls the session record
// afterward so the table always reflects what Store 1 actually has, rather
// than trusting an optimistic local update.
export default function EditableResourceTable({
  table,
  fields,
  columns,
  rows,
  emptyMessage = 'No records found.',
  sessionId,
  onChange,
}) {
  const [adding, setAdding] = useState(false);
  const [newItem, setNewItem] = useState(emptyForm(fields));
  const [editingId, setEditingId] = useState(null);
  const [editItem, setEditItem] = useState({});
  const [busyId, setBusyId] = useState(null);
  const [error, setError] = useState(null);

  const editable = Boolean(sessionId);

  async function handleAdd(e) {
    e.preventDefault();
    setError(null);
    setBusyId('new');
    try {
      await addResource(sessionId, table, newItem);
      setNewItem(emptyForm(fields));
      setAdding(false);
      await onChange();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyId(null);
    }
  }

  function startEdit(row) {
    setEditingId(row.id);
    setEditItem(Object.fromEntries(fields.map((f) => [f.key, row[f.key] ?? ''])));
  }

  async function handleSaveEdit(rowId) {
    setError(null);
    setBusyId(rowId);
    try {
      await editResource(sessionId, table, rowId, editItem);
      setEditingId(null);
      await onChange();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyId(null);
    }
  }

  async function handleRemove(rowId) {
    if (!window.confirm('Remove this record? It will be marked ended, not deleted.')) return;
    setError(null);
    setBusyId(rowId);
    try {
      await removeResource(sessionId, table, rowId);
      await onChange();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div>
      {error && (
        <div className="alert alert--error edit-error">
          <strong>Error:</strong> {error}
        </div>
      )}

      {(!rows || rows.length === 0) && !adding ? (
        <p className="empty-message">{emptyMessage}</p>
      ) : (
        <div className="table-wrapper">
          <table className="resource-table">
            <thead>
              <tr>
                {columns.map((col) => (
                  <th key={col.key}>{col.label}</th>
                ))}
                {editable && <th>Actions</th>}
              </tr>
            </thead>
            <tbody>
              {(rows || []).map((row) => {
                const isEditing = editingId === row.id;
                const rowBusy = busyId === row.id;
                return (
                  <tr key={row.id ?? row.name}>
                    {columns.map((col) => {
                      const field = fields.find((f) => f.key === col.key);
                      if (isEditing && field) {
                        return (
                          <td key={col.key}>
                            <Field
                              field={field}
                              value={editItem[field.key] ?? ''}
                              onChange={(v) => setEditItem((s) => ({ ...s, [field.key]: v }))}
                              disabled={rowBusy}
                            />
                          </td>
                        );
                      }
                      return <td key={col.key}>{row[col.key] ?? '—'}</td>;
                    })}
                    {editable && (
                      <td className="row-actions">
                        {isEditing ? (
                          <>
                            <button
                              className="btn btn--sm btn--primary"
                              disabled={rowBusy}
                              onClick={() => handleSaveEdit(row.id)}
                            >
                              Save
                            </button>
                            <button
                              className="btn btn--sm"
                              disabled={rowBusy}
                              onClick={() => setEditingId(null)}
                            >
                              Cancel
                            </button>
                          </>
                        ) : (
                          <>
                            <button
                              className="btn btn--sm"
                              disabled={busyId != null}
                              onClick={() => startEdit(row)}
                            >
                              Edit
                            </button>
                            <button
                              className="btn btn--sm btn--danger"
                              disabled={busyId != null}
                              onClick={() => handleRemove(row.id)}
                            >
                              {rowBusy ? '…' : 'Remove'}
                            </button>
                          </>
                        )}
                      </td>
                    )}
                  </tr>
                );
              })}

              {adding && (
                <tr>
                  {columns.map((col) => {
                    const field = fields.find((f) => f.key === col.key);
                    if (!field) return <td key={col.key} />;
                    return (
                      <td key={col.key}>
                        <Field
                          field={field}
                          value={newItem[field.key]}
                          onChange={(v) => setNewItem((s) => ({ ...s, [field.key]: v }))}
                          disabled={busyId === 'new'}
                        />
                      </td>
                    );
                  })}
                  <td className="row-actions">
                    <button
                      className="btn btn--sm btn--primary"
                      disabled={busyId === 'new'}
                      onClick={handleAdd}
                    >
                      Save
                    </button>
                    <button
                      className="btn btn--sm"
                      disabled={busyId === 'new'}
                      onClick={() => {
                        setAdding(false);
                        setNewItem(emptyForm(fields));
                      }}
                    >
                      Cancel
                    </button>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {editable && !adding && (
        <button className="btn btn--add" onClick={() => setAdding(true)}>
          + Add
        </button>
      )}
    </div>
  );
}
