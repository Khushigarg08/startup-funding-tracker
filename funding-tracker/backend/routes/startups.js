const router = require('express').Router();
const pool = require('../db');

function toInt(value, fallback) {
  const n = Number.parseInt(value, 10);
  return Number.isFinite(n) ? n : fallback;
}

function buildFilters(query) {
  const where = [];
  const values = [];
  let i = 1;

  const addEq = (field, val) => {
    where.push(`${field} = $${i}`);
    values.push(val);
    i += 1;
  };

  if (query.sector) addEq('sector', query.sector);
  if (query.funding_round) addEq('funding_round', query.funding_round);
  if (query.city) addEq('city', query.city);
  if (query.lead_priority) addEq('lead_priority', query.lead_priority);

  if (query.min_score) {
    const minScore = toInt(query.min_score, null);
    if (minScore !== null) {
      where.push(`lead_score >= $${i}`);
      values.push(minScore);
      i += 1;
    }
  }

  return { where, values };
}

router.get('/startups', async (req, res) => {
  try {
    const page = Math.max(1, toInt(req.query.page, 1));
    const pageSize = Math.min(100, Math.max(1, toInt(req.query.page_size, 20)));
    const offset = (page - 1) * pageSize;

    const { where, values } = buildFilters(req.query);
    const whereSql = where.length ? `WHERE ${where.join(' AND ')}` : '';

    const dataSql = `
      SELECT
        id, startup_name, funding_amount_raw, funding_amount_usd_mn,
        funding_round, sector, investor_names, city, date_published,
        days_since_funding, date_was_estimated, article_url, source,
        lead_score, lead_priority, scraped_at
      FROM startup_funding
      ${whereSql}
      ORDER BY lead_score DESC, date_published DESC
      LIMIT $${values.length + 1} OFFSET $${values.length + 2};
    `;

    const countSql = `
      SELECT COUNT(*)::int AS count
      FROM startup_funding
      ${whereSql};
    `;

    const dataParams = values.concat([pageSize, offset]);

    const [dataResult, countResult] = await Promise.all([
      pool.query(dataSql, dataParams),
      pool.query(countSql, values)
    ]);

    const total = countResult.rows[0] ? countResult.rows[0].count : 0;
    const totalPages = total === 0 ? 1 : Math.ceil(total / pageSize);

    res.status(200).json({
      total,
      page,
      page_size: pageSize,
      total_pages: totalPages,
      results: dataResult.rows
    });
  } catch (err) {
    res.status(500).json({ error: 'Internal server error' });
  }
});

router.get('/startups/:id', async (req, res) => {
  try {
    const { id } = req.params;
    const result = await pool.query(
      `
      SELECT
        id, startup_name, funding_amount_raw, funding_amount_usd_mn,
        funding_round, sector, investor_names, city, date_published,
        days_since_funding, date_was_estimated, article_url, source,
        lead_score, lead_priority, scraped_at
      FROM startup_funding
      WHERE id = $1;
      `,
      [id]
    );

    if (!result.rows.length) {
      return res.status(404).json({ error: 'Not found' });
    }
    return res.status(200).json(result.rows[0]);
  } catch (err) {
    return res.status(500).json({ error: 'Internal server error' });
  }
});

router.get('/stats', async (req, res) => {
  try {
    const queries = [
      pool.query('SELECT COUNT(*)::int AS total_startups FROM startup_funding;'),
      pool.query('SELECT COALESCE(SUM(funding_amount_usd_mn), 0)::float AS total_funding_usd_mn FROM startup_funding;'),
      pool.query('SELECT COALESCE(AVG(lead_score), 0)::float AS avg_lead_score FROM startup_funding;'),
      pool.query(
        `
        SELECT COUNT(*)::int AS new_this_week
        FROM startup_funding
        WHERE days_since_funding <= 7;
        `
      ),
      pool.query(
        `
        SELECT sector, COUNT(*)::int AS count
        FROM startup_funding
        GROUP BY sector
        ORDER BY count DESC
        LIMIT 10;
        `
      ),
      pool.query(
        `
        SELECT city, COUNT(*)::int AS count
        FROM startup_funding
        GROUP BY city
        ORDER BY count DESC
        LIMIT 10;
        `
      ),
      pool.query(
        `
        SELECT date_published, COALESCE(SUM(funding_amount_usd_mn), 0)::float AS total_funding
        FROM startup_funding
        GROUP BY date_published
        ORDER BY date_published ASC
        LIMIT 60;
        `
      ),
      pool.query(
        `
        SELECT lead_priority AS priority, COUNT(*)::int AS count
        FROM startup_funding
        GROUP BY lead_priority
        ORDER BY count DESC;
        `
      )
    ];

    const [
      totalStartups,
      totalFunding,
      avgLeadScore,
      newThisWeek,
      topSectors,
      topCities,
      fundingTrend,
      priorityDist
    ] = await Promise.all(queries);

    res.status(200).json({
      total_startups: totalStartups.rows[0].total_startups,
      total_funding_usd_mn: totalFunding.rows[0].total_funding_usd_mn,
      avg_lead_score: avgLeadScore.rows[0].avg_lead_score,
      new_this_week: newThisWeek.rows[0].new_this_week,
      top_sectors: topSectors.rows,
      top_cities: topCities.rows,
      funding_trend: fundingTrend.rows,
      priority_distribution: priorityDist.rows
    });
  } catch (err) {
    res.status(500).json({ error: 'Internal server error' });
  }
});

router.get('/filters', async (req, res) => {
  try {
    const [sectors, rounds, cities, priorities] = await Promise.all([
      pool.query('SELECT DISTINCT sector FROM startup_funding WHERE sector IS NOT NULL ORDER BY sector ASC;'),
      pool.query('SELECT DISTINCT funding_round FROM startup_funding WHERE funding_round IS NOT NULL ORDER BY funding_round ASC;'),
      pool.query('SELECT DISTINCT city FROM startup_funding WHERE city IS NOT NULL ORDER BY city ASC;'),
      pool.query('SELECT DISTINCT lead_priority FROM startup_funding WHERE lead_priority IS NOT NULL ORDER BY lead_priority ASC;')
    ]);

    res.status(200).json({
      sectors: sectors.rows.map((r) => r.sector),
      funding_rounds: rounds.rows.map((r) => r.funding_round),
      cities: cities.rows.map((r) => r.city),
      lead_priorities: priorities.rows.map((r) => r.lead_priority)
    });
  } catch (err) {
    res.status(500).json({ error: 'Internal server error' });
  }
});

router.get('/health', async (req, res) => {
  try {
    let dbConnected = true;
    try {
      await pool.query('SELECT 1;');
    } catch (e) {
      dbConnected = false;
    }

    res.status(200).json({
      status: 'ok',
      timestamp: new Date().toISOString(),
      db_connected: dbConnected
    });
  } catch (err) {
    res.status(500).json({ status: 'error', timestamp: new Date().toISOString(), db_connected: false });
  }
});

router.get('/', async (req, res) => {
  res.status(200).json({
    message: 'Indian Startup Funding Intelligence Tool API',
    version: '1.0.0',
    endpoints: [
      'GET /api/health',
      'GET /api/filters',
      'GET /api/stats',
      'GET /api/startups',
      'GET /api/startups/:id'
    ]
  });
});

module.exports = router;

