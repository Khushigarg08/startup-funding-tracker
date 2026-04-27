import React, { useEffect, useState } from 'react';
import axios from 'axios';

import './App.css';
import StatsBar from './components/StatsBar';
import Filters from './components/Filters';
import StartupTable from './components/StartupTable';
import Charts from './components/Charts';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

export default function App() {
  const [startups, setStartups] = useState([]);
  const [stats, setStats] = useState(null);
  const [filterOptions, setFilterOptions] = useState(null);
  const [filters, setFilters] = useState({
    sector: '',
    funding_round: '',
    lead_priority: '',
    city: '',
    min_score: 1
  });
  const [pagination, setPagination] = useState({
    total: 0,
    page: 1,
    page_size: 20,
    total_pages: 1
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    setError('');

    const fetchAll = async () => {
      try {
        const [statsRes, filtersRes, startupsRes] = await Promise.all([
          axios.get(`${API_BASE}/stats`),
          axios.get(`${API_BASE}/filters`),
          axios.get(`${API_BASE}/startups`, { params: { page: 1, page_size: 20 } })
        ]);

        if (!mounted) return;
        setStats(statsRes.data);
        setFilterOptions(filtersRes.data);
        setStartups(startupsRes.data.results || []);
        setPagination({
          total: startupsRes.data.total || 0,
          page: startupsRes.data.page || 1,
          page_size: startupsRes.data.page_size || 20,
          total_pages: startupsRes.data.total_pages || 1
        });
      } catch (e) {
        if (!mounted) return;
        setError('Failed to load data from API. Check backend is running and REACT_APP_API_URL is correct.');
      } finally {
        if (!mounted) return;
        setLoading(false);
      }
    };

    fetchAll();
    return () => {
      mounted = false;
    };
  }, []);

  const fetchStartups = async (nextFilters, page) => {
    setLoading(true);
    setError('');
    try {
      const params = {};
      Object.keys(nextFilters).forEach((k) => {
        const v = nextFilters[k];
        if (v === '' || v === null || v === undefined) return;
        params[k] = v;
      });
      params.page = page;
      params.page_size = pagination.page_size;

      const res = await axios.get(`${API_BASE}/startups`, { params });
      setStartups(res.data.results || []);
      setPagination({
        total: res.data.total || 0,
        page: res.data.page || page,
        page_size: res.data.page_size || pagination.page_size,
        total_pages: res.data.total_pages || 1
      });
    } catch (e) {
      setError('Failed to fetch startups. Try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleFilterChange = (newFilters) => {
    setFilters(newFilters);
    setPagination((p) => ({ ...p, page: 1 }));
    fetchStartups(newFilters, 1);
  };

  const handlePageChange = (newPage) => {
    fetchStartups(filters, newPage);
  };

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-inner">
          <h1>Indian Startup Funding Intelligence</h1>
          <p>Automatically track newly funded Indian startups as high-intent B2B leads.</p>
        </div>
      </header>

      <main className="app-main">
        {error ? <div className="error-banner">{error}</div> : null}

        <StatsBar stats={stats} />

        <div className="content-grid">
          <aside>
            <Filters
              options={filterOptions}
              value={filters}
              onChange={handleFilterChange}
            />
          </aside>
          <section>
            {loading ? (
              <div className="loading">
                <div className="dot" />
                <div className="dot" />
                <div className="dot" />
              </div>
            ) : (
              <StartupTable
                startups={startups}
                pagination={pagination}
                onPageChange={handlePageChange}
              />
            )}
          </section>
        </div>

        <Charts stats={stats} startups={startups} />
      </main>

      <footer className="app-footer">
        <p>Auto-refresh pipeline runs every 24 hours (IST). Data source credit: YourStory / Inc42.</p>
      </footer>
    </div>
  );
}

