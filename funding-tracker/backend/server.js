require('dotenv').config();

const express = require('express');
const cors = require('cors');

const app = express();

app.use(cors());
app.use(express.json({ limit: '1mb' }));
app.use(express.urlencoded({ extended: true }));

app.use('/api', require('./routes/startups'));

app.get('/', (req, res) => {
  res.status(200).json({
    message: 'Indian Startup Funding Intelligence Tool',
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

app.use((req, res) => {
  res.status(404).json({ error: 'Not found' });
});

app.use((err, req, res, next) => {
  // if something weird happens, don't leak internals to client
  // eslint-disable-next-line no-unused-vars
  res.status(500).json({ error: 'Internal server error' });
});

const PORT = process.env.PORT ? Number(process.env.PORT) : 8000;
app.listen(PORT, () => {
  console.log(`${new Date().toISOString()} - INFO - Server listening on port ${PORT}`);
});

