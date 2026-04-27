import React, { useEffect, useState } from 'react';
import './Filters.css';

export default function Filters({ options, value, onChange }) {
  const [draft, setDraft] = useState(value);

  useEffect(() => {
    setDraft(value);
  }, [value]);

  const sectors = (options && options.sectors) || [];
  const rounds = (options && options.funding_rounds) || [];
  const cities = (options && options.cities) || [];
  const priorities = (options && options.lead_priorities) || [];

  const update = (patch) => {
    setDraft((d) => ({ ...d, ...patch }));
  };

  const apply = () => {
    onChange({ ...draft, min_score: Number(draft.min_score || 1) });
  };

  const reset = () => {
    const fresh = { sector: '', funding_round: '', lead_priority: '', city: '', min_score: 1 };
    setDraft(fresh);
    onChange(fresh);
  };

  return (
    <div className="filters-card">
      <h3>Filters</h3>

      <label className="field">
        <span>Sector</span>
        <select value={draft.sector} onChange={(e) => update({ sector: e.target.value })}>
          <option value="">All</option>
          {sectors.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </label>

      <label className="field">
        <span>Funding Round</span>
        <select value={draft.funding_round} onChange={(e) => update({ funding_round: e.target.value })}>
          <option value="">All</option>
          {rounds.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>
      </label>

      <label className="field">
        <span>Lead Priority</span>
        <select value={draft.lead_priority} onChange={(e) => update({ lead_priority: e.target.value })}>
          <option value="">All</option>
          {['High', 'Medium', 'Low']
            .filter((p) => priorities.includes(p) || priorities.length === 0)
            .map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
        </select>
      </label>

      <label className="field">
        <span>City</span>
        <select value={draft.city} onChange={(e) => update({ city: e.target.value })}>
          <option value="">All</option>
          {cities.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </label>

      <div className="field">
        <span>
          Min Lead Score <strong className="score-pill">{draft.min_score}</strong>
        </span>
        <input
          type="range"
          min="1"
          max="10"
          step="1"
          value={draft.min_score}
          onChange={(e) => update({ min_score: Number(e.target.value) })}
        />
      </div>

      <div className="buttons">
        <button className="btn primary" onClick={apply}>
          Apply Filters
        </button>
        <button className="btn outline" onClick={reset}>
          Reset
        </button>
      </div>
    </div>
  );
}

