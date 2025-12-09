# keep_alive.py
from flask import Flask
from threading import Thread
import os

app = Flask('')

@app.route('/')
def home():
    """Page d'accueil simple pour la surveillance de Replit."""
    return "Bot Spotify Tracker est en ligne et fonctionne !"

def run():
    """Lance le serveur Flask."""
    port = os.environ.get('PORT', 8080)
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    """Démarre le serveur Flask dans un thread séparé."""
    t = Thread(target=run)
    t.start()