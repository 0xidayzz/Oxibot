# helpers/database.py
import sqlite3
from datetime import datetime
import pytz

DATABASE_PATH = 'data/spotify_db.sqlite'
PARIS_TZ = pytz.timezone('Europe/Paris')

def get_db_connection():
    """Crée et retourne une connexion à la base de données."""
    # Assure l'existence du dossier data
    if not os.path.exists('data'):
        os.makedirs('data')
        
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def setup_database():
    """Initialise les tables de la base de données."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS listening_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            track_id TEXT NOT NULL,
            title TEXT NOT NULL,
            artist_name TEXT NOT NULL,
            album_name TEXT,
            played_at TEXT NOT NULL,
            duration_ms INTEGER NOT NULL,
            UNIQUE(track_id, played_at)
        );
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS server_settings (
            guild_id INTEGER PRIMARY KEY,
            music_channel_id INTEGER,
            announcement_channel_id INTEGER,
            wrapped_channel_id INTEGER,
            follow_channel_id INTEGER,
            theme TEXT DEFAULT 'default'
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS followed_artists (
            artist_id TEXT PRIMARY KEY,
            artist_name TEXT NOT NULL,
            guild_id INTEGER
        );
    """)

    conn.commit()
    conn.close()

def log_track(track_info):
    """Enregistre une piste écoutée dans la base de données."""
    conn = get_db_connection()
    cursor = conn.cursor()
    played_at_utc = datetime.now(PARIS_TZ).astimezone(pytz.utc).strftime('%Y-%m-%d %H:%M:%S')

    try:
        cursor.execute("""
            INSERT INTO listening_history 
            (track_id, title, artist_name, album_name, played_at, duration_ms) 
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            track_info['id'], 
            track_info['name'], 
            track_info['artist'], 
            track_info['album'],
            played_at_utc,
            track_info['duration_ms']
        ))
        conn.commit()
    except sqlite3.IntegrityError:
        pass 
    finally:
        conn.close()

def get_stats_for_presence():
    """Calcule et retourne les stats pour la présence du bot."""
    conn = get_db_connection()
    
    total_duration_ms = conn.execute(
        "SELECT SUM(duration_ms) FROM listening_history"
    ).fetchone()[0] or 0
    total_hours = total_duration_ms / (1000 * 60 * 60)
    
    top_artist = conn.execute("""
        SELECT artist_name, COUNT(artist_name) as count 
        FROM listening_history 
        GROUP BY artist_name 
        ORDER BY count DESC 
        LIMIT 1
    """).fetchone()
    
    last_track = conn.execute("""
        SELECT title, artist_name, played_at 
        FROM listening_history 
        ORDER BY played_at DESC 
        LIMIT 1
    """).fetchone()
    
    conn.close()
    
    return {
        'total_hours': total_hours,
        'top_artist': top_artist['artist_name'] if top_artist else "N/A",
        'last_track': f"{last_track['title']} par {last_track['artist_name']}" if last_track else "N/A"
    }