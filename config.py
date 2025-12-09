import os
from dotenv import load_dotenv
import pytz

load_dotenv()

# Discord
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

# Spotify
SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
SPOTIFY_REDIRECT_URI = os.getenv('SPOTIFY_REDIRECT_URI', 'http://localhost:8888/callback')
SPOTIFY_SCOPE = 'user-read-currently-playing user-read-playback-state user-top-read user-read-recently-played user-follow-read'

# MySQL
MYSQL_CONFIG = {
    'host': os.getenv('MYSQL_HOST', 'localhost'),
    'user': os.getenv('MYSQL_USER', 'root'),
    'password': os.getenv('MYSQL_PASSWORD'),
    'database': os.getenv('MYSQL_DATABASE', 'spotify_tracker')
}

# Timezone
TIMEZONE = pytz.timezone('Europe/Paris')

# Thème par défaut
DEFAULT_THEME = {
    'color': 0x9B59B6,  # Violet
    'emojis': {
        'music': '🎵',
        'artist': '🎤',
        'album': '💿',
        'stats': '📊',
        'fire': '🔥',
        'trophy': '🏆',
        'chart': '📈',
        'calendar': '📅',
        'headphones': '🎧',
        'new': '✨'
    }
}

# Paliers
MILESTONES = {
    'listening_time': [10, 50, 100, 500, 1000, 5000, 10000],  # heures
    'tracks_count': [100, 500, 1000, 5000, 10000, 50000],
    'artists_count': [10, 50, 100, 500, 1000]
}