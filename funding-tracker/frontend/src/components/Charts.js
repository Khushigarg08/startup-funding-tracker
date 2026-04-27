import React from 'react';
import './Charts.css';

import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  LineChart,
  Line,
  Cell
} from 'recharts';

function normalizePriorityData(stats) {
  const arr = (stats && stats.priority_distribution) || [];
  return arr.map((r) => ({
    priority: r.priority,
    count: Number(r.count || 0)
  }));
}

const COLORS = {
  High: '#10b981',
  Medium: '#f59e0b',
  Low: '#ef4444'
};

export default function Charts({ stats }) {
  const topSectors = (stats && stats.top_sectors) || [];
  const topCities = (stats && stats.top_cities) || [];
  const fundingTrend = (stats && stats.funding_trend) || [];
  const priorityData = normalizePriorityData(stats);

  return (
    <div className="charts">
      <div className="charts-grid">
        <div className="chart-card">
          <h3>Top Sectors</h3>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={topSectors} layout="vertical" margin={{ top: 10, right: 10, bottom: 10, left: 10 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" />
              <YAxis type="category" dataKey="sector" width={90} />
              <Tooltip />
              <Bar dataKey="count" fill="var(--blue)" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-card">
          <h3>Top Cities</h3>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={topCities} layout="vertical" margin={{ top: 10, right: 10, bottom: 10, left: 10 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" />
              <YAxis type="category" dataKey="city" width={90} />
              <Tooltip />
              <Bar dataKey="count" fill="var(--green)" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-card">
          <h3>Funding Trend</h3>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={fundingTrend} margin={{ top: 10, right: 10, bottom: 10, left: 10 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date_published" />
              <YAxis />
              <Tooltip />
              <Line type="monotone" dataKey="total_funding" stroke="var(--yellow)" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-card">
          <h3>Lead Priority Distribution</h3>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={priorityData} margin={{ top: 10, right: 10, bottom: 10, left: 10 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="priority" />
              <YAxis />
              <Tooltip />
              <Bar dataKey="count">
                {priorityData.map((entry) => (
                  <Cell key={entry.priority} fill={COLORS[entry.priority] || '#64748b'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

