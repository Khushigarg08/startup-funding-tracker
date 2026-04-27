require('dotenv').config();

const { Pool } = require('pg');

const pool = new Pool({
  host: process.env.DB_HOST,
  port: process.env.DB_PORT ? Number(process.env.DB_PORT) : 5432,
  database: process.env.DB_NAME,
  user: process.env.DB_USER,
  password: process.env.DB_PASSWORD,
  max: 10,
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 2000
});

pool
  .query('SELECT NOW()')
  .then((res) => {
    console.log(`${new Date().toISOString()} - INFO - PostgreSQL connected: ${res.rows[0].now}`);
  })
  .catch((err) => {
    console.error(`${new Date().toISOString()} - ERROR - PostgreSQL connection failed`, err.message);
  });

module.exports = pool;

