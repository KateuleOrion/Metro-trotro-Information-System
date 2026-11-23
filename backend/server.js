require('dotenv').config();
const express = require('express');
const syncRoutes = require('./sync');

const app = express();
app.use(express.json({ limit: '1mb' }));

app.get('/health', (req, res) => res.json({ status: 'ok' }));
app.use('/sync', syncRoutes);

const port = process.env.PORT || 3000;
app.listen(port, () => console.log(`Backend running on port ${port}`));
