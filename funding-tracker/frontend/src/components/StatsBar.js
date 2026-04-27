import React from 'react';
import './StatsBar.css';

function getHighCount(stats) {
  if (!stats || !Array.isArray(stats.priority_distribution)) return 0;
  const row = stats.priority_distribution.find((r) => String(r.priority).toLowerCase() === 'high');
  return row ? Number(row.count || 0) : 0;
}

export default function StatsBar({ stats }) {
  const totalStartups = stats ? Number(stats.total_startups || 0) : 0;
  const totalFunding = stats ? Number(stats.total_funding_usd_mn || 0) : 0;
  const avgScore = stats ? Number(stats.avg_lead_score || 0) : 0;
  const newThisWeek = stats ? Number(stats.new_this_week || 0) : 0;
  const highLeads = getHighCount(stats);

  const cards = [
    { icon: '🏢', label: 'Total Startups', value: totalStartups.toLocaleString() },
    { icon: '💰', label: 'Total Funding (USD Mn)', value: totalFunding.toFixed(2) },
    { icon: '⭐', label: 'Avg Lead Score', value: avgScore.toFixed(2) },
    { icon: '🆕', label: 'New This Week', value: newThisWeek.toLocaleString() },
    { icon: '🔥', label: 'High Priority Leads', value: highLeads.toLocaleString() }
  ];

  return (
    <div className="stats-bar">
      {cards.map((c) => (
        <div key={c.label} className="stat-card">
          <div className="stat-icon">{c.icon}</div>
          <div className="stat-meta">
            <div className="stat-value">{c.value}</div>
            <div className="stat-label">{c.label}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

