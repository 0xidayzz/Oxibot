// keep-alive.js - Maintient le bot actif sur Replit
const express = require('express');

function keepAlive() {
  const app = express();
  const port = process.env.PORT || 5000;

  app.get('/', (req, res) => {
    res.status(200).send(`
      <!DOCTYPE html>
      <html>
      <head>
        <title>Spotify Tracker Bot</title>
        <style>
          body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1DB954 0%, #191414 100%);
            color: white;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
          }
          .container {
            text-align: center;
            background: rgba(0, 0, 0, 0.7);
            padding: 40px;
            border-radius: 20px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
          }
          h1 {
            font-size: 3em;
            margin: 0;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.5);
          }
          .emoji {
            font-size: 5em;
            animation: pulse 2s infinite;
          }
          @keyframes pulse {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.1); }
          }
          .status {
            background: #1DB954;
            padding: 10px 20px;
            border-radius: 10px;
            margin-top: 20px;
            font-weight: bold;
          }
          .info {
            margin-top: 20px;
            opacity: 0.8;
          }
        </style>
      </head>
      <body>
        <div class="container">
          <div class="emoji">🎵</div>
          <h1>Spotify Tracker Bot</h1>
          <div class="status">✅ Bot en ligne</div>
          <div class="info">
            <p>Le bot Discord est actif et prêt à tracker ta musique !</p>
            <p>Uptime: ${Math.floor(process.uptime() / 60)} minutes</p>
          </div>
        </div>
      </body>
      </html>
    `);
  });

  app.get('/health', (req, res) => {
    res.status(200).json({
      status: 'healthy',
      uptime: process.uptime(),
      timestamp: new Date().toISOString()
    });
  });

  app.get('/ping', (req, res) => {
    res.status(200).send('pong');
  });

  app.listen(port, '0.0.0.0', () => {
    console.log(`✅ Keep-alive serveur démarré sur le port ${port}`);
  });
}

module.exports = keepAlive;