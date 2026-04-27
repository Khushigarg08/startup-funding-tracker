import React from 'react';
import './StartupTable.css';

function scoreClass(score) {
  const s = Number(score || 0);
  if (s >= 7) return 'score high';
  if (s >= 4) return 'score medium';
  return 'score low';
}

function priorityClass(priority) {
  const p = String(priority || '').toLowerCase();
  if (p === 'high') return 'priority high';
  if (p === 'medium') return 'priority medium';
  if (p === 'low') return 'priority low';
  return 'priority unknown';
}

function toCsvValue(v) {
  const s = v === null || v === undefined ? '' : String(v);
  const escaped = s.replace(/"/g, '""');
  return `"${escaped}"`;
}

function exportCsv(rows) {
  const headers = [
    'startup_name',
    'sector',
    'funding_round',
    'funding_amount_usd_mn',
    'investor_names',
    'city',
    'date_published',
    'lead_score',
    'lead_priority',
    'article_url'
  ];

  const lines = [headers.join(',')];
  rows.forEach((r) => {
    const line = headers.map((h) => toCsvValue(r[h]));
    lines.push(line.join(','));
  });

  const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `startup_funding_${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export default function StartupTable({ startups, pagination, onPageChange }) {
  const page = pagination ? Number(pagination.page || 1) : 1;
  const totalPages = pagination ? Number(pagination.total_pages || 1) : 1;

  return (
    <div className="table-card">
      <div className="table-head">
        <div className="title">
          <h3>Funded Startups</h3>
          <p>Sorted by lead score (desc) and most recent funding.</p>
        </div>
        <button className="export-btn" onClick={() => exportCsv(startups || [])}>
          Export CSV
        </button>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Startup Name</th>
              <th>Sector</th>
              <th>Round</th>
              <th>Funding (USD Mn)</th>
              <th>Investors</th>
              <th>City</th>
              <th>Date</th>
              <th>Lead Score</th>
              <th>Priority</th>
            </tr>
          </thead>
          <tbody>
            {(startups || []).map((s) => (
              <tr key={s.id}>
                <td className="startup">
                  <a href={s.article_url} target="_blank" rel="noreferrer">
                    {s.startup_name}
                  </a>
                </td>
                <td>
                  <span className="badge">{s.sector || 'Other'}</span>
                </td>
                <td>{s.funding_round || 'Undisclosed'}</td>
                <td>{s.funding_amount_usd_mn !== null && s.funding_amount_usd_mn !== undefined ? Number(s.funding_amount_usd_mn).toFixed(2) : '-'}</td>
                <td className="investors" title={s.investor_names || ''}>
                  {s.investor_names || 'Unknown'}
                </td>
                <td>{s.city || 'Unknown'}</td>
                <td>{s.date_published || '-'}</td>
                <td>
                  <span className={scoreClass(s.lead_score)}>{Number(s.lead_score || 0)}</span>
                </td>
                <td>
                  <span className={priorityClass(s.lead_priority)}>{s.lead_priority || 'Unknown'}</span>
                </td>
              </tr>
            ))}
            {!startups || startups.length === 0 ? (
              <tr>
                <td colSpan="9" className="empty">
                  No results. Adjust filters and try again.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>

      <div className="pagination">
        <button className="page-btn" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
          Prev
        </button>
        <div className="page-indicator">
          Page <strong>{page}</strong> of <strong>{totalPages}</strong>
        </div>
        <button className="page-btn" disabled={page >= totalPages} onClick={() => onPageChange(page + 1)}>
          Next
        </button>
      </div>
    </div>
  );
}

