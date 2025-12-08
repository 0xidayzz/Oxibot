import discord
from discord.ext import commands, tasks
import requests
from datetime import datetime, timedelta, time
import os
from dotenv import load_dotenv
import base64
import sqlite3
import json
from collections import Counter, defaultdict
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import io

# Charge les variables d'environnement
load_dotenv()

# Configuration
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
GITHUB_USERNAME = os.getenv('GITHUB_USERNAME')
SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
SPOTIFY_REFRESH_TOKEN = os.getenv('SPOTIFY_REFRESH_TOKEN')

# ========== THÈMES ==========
THEMES = {
    'violet': {
        'primary': 0x9B59B6,
        'secondary': 0xBB8FCE,
        'accent': 0xE8DAEF,
        'success': 0x52BE80,
        'warning': 0xF39C12,
        'error': 0xE74C3C,
        'emojis': {
            'music': '🎵',
            'fire': '🔥',
            'star': '⭐',
            'trophy': '🏆',
            'party': '🎉',
            'rocket': '🚀'
        }
    },
    'ocean': {
        'primary': 0x3498DB,
        'secondary': 0x5DADE2,
        'accent': 0xAED6F1,
        'success': 0x1ABC9C,
        'warning': 0xF39C12,
        'error': 0xE74C3C,
        'emojis': {
            'music': '🌊',
            'fire': '💙',
            'star': '✨',
            'trophy': '🏅',
            'party': '🎊',
            'rocket': '⚡'
        }
    },
    'sunset': {
        'primary': 0xFF6B6B,
        'secondary': 0xFFE66D,
        'accent': 0xFF8E53,
        'success': 0x4ECDC4,
        'warning': 0xF39C12,
        'error': 0xE74C3C,
        'emojis': {
            'music': '🌅',
            'fire': '🔥',
            'star': '🌟',
            'trophy': '🏆',
            'party': '🎈',
            'rocket': '🚀'
        }
    },
    'forest': {
        'primary': 0x27AE60,
        'secondary': 0x52BE80,
        'accent': 0xA9DFBF,
        'success': 0x58D68D,
        'warning': 0xF39C12,
        'error': 0xE74C3C,
        'emojis': {
            'music': '🍃',
            'fire': '🌿',
            'star': '⭐',
            'trophy': '🏆',
            'party': '🌳',
            'rocket': '🚀'
        }
    }
}

class ThemeManager:
    """Gestion des thèmes personnalisés"""
    
    def __init__(self, db):
        self.db = db
        self.current_theme = self.load_theme()
    
    def load_theme(self):
        """Charge le thème depuis la DB"""
        theme_name = self.db.get_config('theme', 'violet')
        return THEMES.get(theme_name, THEMES['violet'])
    
    def set_theme(self, theme_name):
        """Change le thème"""
        if theme_name.lower() in THEMES:
            self.db.save_config('theme', theme_name.lower())
            self.current_theme = THEMES[theme_name.lower()]
            return True
        return False
    
    def get_color(self, color_type='primary'):
        """Récupère une couleur du thème"""
        return self.current_theme.get(color_type, 0x9B59B6)
    
    def get_emoji(self, emoji_type):
        """Récupère un emoji du thème"""
        return self.current_theme['emojis'].get(emoji_type, '🎵')

class Database:
    """Gestion de la base de données SQLite"""
    
    def __init__(self, db_name='bot_data.db'):
        self.db_name = db_name
        self.init_database()
    
    def get_connection(self):
        return sqlite3.connect(self.db_name)
    
    def init_database(self):
        """Initialise les tables de la base de données"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Table pour les écoutes Spotify avec genres
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS spotify_plays (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                track_id TEXT NOT NULL,
                track_name TEXT NOT NULL,
                artist_name TEXT NOT NULL,
                album_name TEXT,
                duration_ms INTEGER,
                played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                image_url TEXT,
                genres TEXT,
                artist_id TEXT,
                popularity INTEGER,
                valence REAL,
                energy REAL,
                danceability REAL
            )
        ''')
        
        # Table pour suivre les artistes
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS followed_artists (
                artist_id TEXT PRIMARY KEY,
                artist_name TEXT NOT NULL,
                last_check TIMESTAMP,
                last_release_id TEXT
            )
        ''')
        
        # Table pour les nouveautés détectées
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS new_releases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                artist_id TEXT NOT NULL,
                artist_name TEXT NOT NULL,
                album_id TEXT NOT NULL,
                album_name TEXT NOT NULL,
                release_date TEXT,
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                notified INTEGER DEFAULT 0
            )
        ''')
        
        # Table pour les push GitHub
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS github_pushes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT UNIQUE,
                repo_name TEXT NOT NULL,
                pushed_at TIMESTAMP NOT NULL,
                commits_count INTEGER DEFAULT 0,
                commits_data TEXT,
                branch TEXT
            )
        ''')
        
        # Table pour les repositories GitHub
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS github_repos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo_name TEXT UNIQUE NOT NULL,
                description TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP,
                language TEXT,
                stars INTEGER DEFAULT 0,
                url TEXT
            )
        ''')
        
        # Table de configuration
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        ''')
        
        # Table pour les rapports automatiques
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS auto_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_type TEXT NOT NULL,
                generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                data TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def save_spotify_play(self, track_data, genres=None, audio_features=None):
        """Enregistre une écoute Spotify avec genres et features"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        genres_str = ','.join(genres) if genres else None
        
        cursor.execute('''
            INSERT INTO spotify_plays 
            (track_id, track_name, artist_name, album_name, duration_ms, image_url, 
             genres, artist_id, popularity, valence, energy, danceability)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            track_data['id'],
            track_data['name'],
            track_data['artists'][0]['name'],
            track_data['album']['name'],
            track_data['duration_ms'],
            track_data['album']['images'][0]['url'] if track_data['album']['images'] else None,
            genres_str,
            track_data['artists'][0]['id'],
            track_data.get('popularity', 0),
            audio_features.get('valence') if audio_features else None,
            audio_features.get('energy') if audio_features else None,
            audio_features.get('danceability') if audio_features else None
        ))
        
        conn.commit()
        conn.close()
    
    def add_followed_artist(self, artist_id, artist_name):
        """Ajoute un artiste au suivi"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO followed_artists (artist_id, artist_name, last_check)
            VALUES (?, ?, ?)
        ''', (artist_id, artist_name, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        
        conn.commit()
        conn.close()
    
    def get_followed_artists(self):
        """Récupère la liste des artistes suivis"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT artist_id, artist_name FROM followed_artists')
        results = cursor.fetchall()
        conn.close()
        return results
    
    def save_new_release(self, artist_id, artist_name, album_id, album_name, release_date):
        """Enregistre une nouvelle sortie"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO new_releases 
                (artist_id, artist_name, album_id, album_name, release_date)
                VALUES (?, ?, ?, ?, ?)
            ''', (artist_id, artist_name, album_id, album_name, release_date))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()
    
    def get_unnotified_releases(self):
        """Récupère les sorties non notifiées"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, artist_name, album_name, release_date
            FROM new_releases
            WHERE notified = 0
        ''')
        results = cursor.fetchall()
        conn.close()
        return results
    
    def mark_release_notified(self, release_id):
        """Marque une sortie comme notifiée"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE new_releases SET notified = 1 WHERE id = ?', (release_id,))
        conn.commit()
        conn.close()
    
    def get_track_play_count(self, track_id=None, artist_name=None):
        """Obtient le nombre d'écoutes d'une track ou d'un artiste"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if track_id:
            cursor.execute('SELECT COUNT(*) FROM spotify_plays WHERE track_id = ?', (track_id,))
        elif artist_name:
            cursor.execute('SELECT COUNT(*) FROM spotify_plays WHERE artist_name LIKE ?', 
                         (f'%{artist_name}%',))
        else:
            cursor.execute('SELECT COUNT(*) FROM spotify_plays')
        
        count = cursor.fetchone()[0]
        conn.close()
        return count
    
    def get_top_tracks(self, limit=10, days=None):
        """Récupère les tracks les plus écoutées"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        query = '''
            SELECT track_name, artist_name, COUNT(*) as play_count, track_id, image_url
            FROM spotify_plays
        '''
        
        if days:
            date_limit = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            query += f" WHERE played_at >= '{date_limit}'"
        
        query += '''
            GROUP BY track_id
            ORDER BY play_count DESC
            LIMIT ?
        '''
        
        cursor.execute(query, (limit,))
        results = cursor.fetchall()
        conn.close()
        return results
    
    def get_top_artists(self, limit=10, days=None):
        """Récupère les artistes les plus écoutés"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        query = '''
            SELECT artist_name, COUNT(*) as play_count
            FROM spotify_plays
        '''
        
        if days:
            date_limit = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            query += f" WHERE played_at >= '{date_limit}'"
        
        query += '''
            GROUP BY artist_name
            ORDER BY play_count DESC
            LIMIT ?
        '''
        
        cursor.execute(query, (limit,))
        results = cursor.fetchall()
        conn.close()
        return results
    
    def get_top_genres(self, limit=10, days=None):
        """Récupère les genres les plus écoutés"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        query = '''
            SELECT genres, COUNT(*) as play_count
            FROM spotify_plays
            WHERE genres IS NOT NULL AND genres != ''
        '''
        
        if days:
            date_limit = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            query += f" AND played_at >= '{date_limit}'"
        
        query += ' ORDER BY play_count DESC'
        
        cursor.execute(query)
        results = cursor.fetchall()
        conn.close()
        
        # Compte les genres individuels
        genre_counter = Counter()
        for genres_str, count in results:
            for genre in genres_str.split(','):
                genre = genre.strip()
                if genre:
                    genre_counter[genre] += count
        
        return genre_counter.most_common(limit)
    
    def get_total_listening_time(self, days=None):
        """Calcule le temps d'écoute total"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        query = 'SELECT SUM(duration_ms) FROM spotify_plays'
        
        if days:
            date_limit = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            query += f" WHERE played_at >= '{date_limit}'"
        
        cursor.execute(query)
        total_ms = cursor.fetchone()[0] or 0
        conn.close()
        
        return total_ms // 60000  # Convertit en minutes
    
    def get_new_discoveries(self, days=7):
        """Récupère les nouvelles musiques découvertes"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        date_limit = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
            SELECT track_name, artist_name, MIN(played_at) as first_play, COUNT(*) as play_count
            FROM spotify_plays
            WHERE played_at >= ?
            GROUP BY track_id
            HAVING first_play >= ?
            ORDER BY first_play DESC
        ''', (date_limit, date_limit))
        
        results = cursor.fetchall()
        conn.close()
        return results
    
    def save_github_push(self, event_data):
        """Enregistre un push GitHub"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO github_pushes 
                (event_id, repo_name, pushed_at, commits_count, commits_data, branch)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                event_data['id'],
                event_data['repo']['name'],
                event_data['created_at'],
                len(event_data['payload'].get('commits', [])),
                json.dumps(event_data['payload'].get('commits', [])),
                event_data['payload'].get('ref', 'unknown').replace('refs/heads/', '')
            ))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()
    
    def get_recent_pushes(self, limit=10):
        """Récupère les derniers pushes"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT repo_name, pushed_at, commits_count, commits_data, branch
            FROM github_pushes
            ORDER BY pushed_at DESC
            LIMIT ?
        ''', (limit,))
        
        results = cursor.fetchall()
        conn.close()
        return results
    
    def get_total_pushes(self):
        """Compte le nombre total de pushes"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM github_pushes')
        count = cursor.fetchone()[0]
        conn.close()
        return count
    
    def save_config(self, key, value):
        """Sauvegarde une configuration"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)', (key, str(value)))
        conn.commit()
        conn.close()
    
    def get_config(self, key, default=None):
        """Récupère une configuration"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT value FROM config WHERE key = ?', (key,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else default
    
    def search_track(self, query):
        """Recherche une track dans l'historique"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT track_name, artist_name, COUNT(*) as play_count, 
                   track_id, image_url, MIN(played_at) as first_play, genres
            FROM spotify_plays
            WHERE track_name LIKE ? OR artist_name LIKE ?
            GROUP BY track_id
            ORDER BY play_count DESC
        ''', (f'%{query}%', f'%{query}%'))
        
        results = cursor.fetchall()
        conn.close()
        return results

class BotAnalytics:
    """Module d'analyse et visualisation avancées"""
    
    def __init__(self, db, theme_manager):
        self.db = db
        self.theme = theme_manager
        plt.style.use('dark_background')
    
    def generate_listening_trend(self, days=30):
        """Génère un graphique d'évolution des écoutes"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        date_limit = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        cursor.execute('''
            SELECT DATE(played_at) as day, COUNT(*) as count
            FROM spotify_plays
            WHERE played_at >= ?
            GROUP BY DATE(played_at)
            ORDER BY day
        ''', (date_limit,))
        
        data = cursor.fetchall()
        conn.close()
        
        if not data:
            return None
        
        dates = [datetime.strptime(d[0], '%Y-%m-%d') for d in data]
        counts = [d[1] for d in data]
        
        # Couleur du thème
        color = f"#{self.theme.get_color('primary'):06x}"
        
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(dates, counts, marker='o', linewidth=2, markersize=6, 
                color=color, label='Écoutes')
        
        ax.set_xlabel('Date', fontsize=12, color='white')
        ax.set_ylabel('Nombre d\'écoutes', fontsize=12, color='white')
        ax.set_title(f'Évolution des écoutes ({days} derniers jours)', 
                    fontsize=14, color='white', pad=20)
        ax.grid(True, alpha=0.3, linestyle='--')
        ax.legend(loc='upper left')
        
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, days//10)))
        plt.xticks(rotation=45)
        
        avg = sum(counts) / len(counts)
        ax.axhline(y=avg, color='orange', linestyle='--', 
                  alpha=0.7, label=f'Moyenne: {avg:.1f}')
        
        plt.tight_layout()
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, facecolor='#2C2F33')
        buf.seek(0)
        plt.close()
        
        return buf
    
    def generate_activity_heatmap(self):
        """Génère une heatmap d'activité"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                CAST(strftime('%w', played_at) AS INTEGER) as day_of_week,
                CAST(strftime('%H', played_at) AS INTEGER) as hour,
                COUNT(*) as count
            FROM spotify_plays
            GROUP BY day_of_week, hour
        ''')
        
        data = cursor.fetchall()
        conn.close()
        
        if not data:
            return None
        
        matrix = [[0 for _ in range(24)] for _ in range(7)]
        for day, hour, count in data:
            matrix[day][hour] = count
        
        fig, ax = plt.subplots(figsize=(14, 6))
        im = ax.imshow(matrix, cmap='YlGn', aspect='auto')
        
        days = ['Dim', 'Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam']
        ax.set_yticks(range(7))
        ax.set_yticklabels(days, color='white')
        ax.set_xticks(range(24))
        ax.set_xticklabels(range(24), color='white')
        
        ax.set_xlabel('Heure de la journée', fontsize=12, color='white')
        ax.set_ylabel('Jour de la semaine', fontsize=12, color='white')
        ax.set_title('Heatmap d\'activité musicale', 
                    fontsize=14, color='white', pad=20)
        
        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label('Nombre d\'écoutes', color='white')
        cbar.ax.yaxis.set_tick_params(color='white')
        plt.setp(plt.getp(cbar.ax.axes, 'yticklabels'), color='white')
        
        plt.tight_layout()
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, facecolor='#2C2F33')
        buf.seek(0)
        plt.close()
        
        return buf
    
    def generate_genre_pie(self, limit=8, days=None):
        """Génère un camembert des genres"""
        genres_data = self.db.get_top_genres(limit, days)
        
        if not genres_data:
            return None
        
        labels = [g[0] for g in genres_data]
        sizes = [g[1] for g in genres_data]
        
        fig, ax = plt.subplots(figsize=(10, 8))
        colors = plt.cm.Set3(range(len(labels)))
        
        wedges, texts, autotexts = ax.pie(
            sizes, labels=labels, autopct='%1.1f%%',
            startangle=90, colors=colors,
            textprops={'color': 'white', 'fontsize': 11}
        )
        
        for autotext in autotexts:
            autotext.set_color('black')
            autotext.set_fontweight('bold')
        
        ax.set_title('Distribution des genres musicaux', 
                    fontsize=14, color='white', pad=20)
        
        plt.tight_layout()
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, facecolor='#2C2F33')
        buf.seek(0)
        plt.close()
        
        return buf
    
    def analyze_listening_patterns(self):
        """Analyse les patterns d'écoute"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                CASE 
                    WHEN CAST(strftime('%H', played_at) AS INTEGER) BETWEEN 6 AND 11 THEN 'Matin'
                    WHEN CAST(strftime('%H', played_at) AS INTEGER) BETWEEN 12 AND 17 THEN 'Après-midi'
                    WHEN CAST(strftime('%H', played_at) AS INTEGER) BETWEEN 18 AND 22 THEN 'Soirée'
                    ELSE 'Nuit'
                END as period,
                artist_name,
                COUNT(*) as count
            FROM spotify_plays
            WHERE played_at >= date('now', '-30 days')
            GROUP BY period, artist_name
        ''')
        
        data = cursor.fetchall()
        conn.close()
        
        patterns = defaultdict(Counter)
        for period, artist, count in data:
            patterns[period][artist] += count
        
        results = {}
        for period, artists in patterns.items():
            if artists:
                top_artist, count = artists.most_common(1)[0]
                results[period] = (top_artist, count)
        
        return results
    
    def calculate_streaks(self):
        """Calcule les streaks d'écoute"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT DISTINCT DATE(played_at) as day
            FROM spotify_plays
            ORDER BY day DESC
        ''')
        
        dates = [datetime.strptime(d[0], '%Y-%m-%d').date() for d in cursor.fetchall()]
        conn.close()
        
        if not dates:
            return 0, 0
        
        current_streak = 0
        today = datetime.now().date()
        
        if dates and dates[0] == today:
            current_streak = 1
            for i in range(1, len(dates)):
                if (dates[i-1] - dates[i]).days == 1:
                    current_streak += 1
                else:
                    break
        elif dates and dates[0] == today - timedelta(days=1):
            current_streak = 1
            for i in range(1, len(dates)):
                if (dates[i-1] - dates[i]).days == 1:
                    current_streak += 1
                else:
                    break
        
        best_streak = 1
        temp_streak = 1
        
        for i in range(1, len(dates)):
            if (dates[i-1] - dates[i]).days == 1:
                temp_streak += 1
                best_streak = max(best_streak, temp_streak)
            else:
                temp_streak = 1
        
        return current_streak, best_streak
    
    def get_mood_analysis(self):
        """Analyse le mood moyen"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT AVG(valence), AVG(energy), AVG(danceability)
            FROM spotify_plays
            WHERE valence IS NOT NULL
            AND played_at >= date('now', '-7 days')
        ''')
        
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0]:
            valence, energy, danceability = result
            
            if valence > 0.6 and energy > 0.6:
                mood = "Énergique et joyeux 🎉"
            elif valence > 0.6 and energy < 0.4:
                mood = "Calme et positif 😌"
            elif valence < 0.4 and energy > 0.6:
                mood = "Intense et sombre 🔥"
            else:
                mood = "Mélancolique et doux 🌙"
            
            return {
                'mood': mood,
                'valence': valence,
                'energy': energy,
                'danceability': danceability
            }
        
        return None

class ProfileUpdater(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.presences = True
        intents.guilds = True
        super().__init__(command_prefix='!', intents=intents)
        
        self.db = Database()
        self.theme_manager = ThemeManager(self.db)
        self.analytics = BotAnalytics(self.db, self.theme_manager)
        self.spotify_access_token = None
        self.last_track_id = None
        self.current_track_data = None
        self.github_repos_count = 0
        
    async def on_ready(self):
        print("\n" + "="*60)
        print(f"✅ Bot connecté: {self.user}")
        print(f"📊 ID: {self.user.id}")
        print(f"🎨 Thème: {self.db.get_config('theme', 'violet')}")
        print("="*60)
        
        # Auto-suivre les artistes favoris
        await self.auto_follow_top_artists()
        
        await self.update_data()
        
        if not self.update_loop.is_running():
            self.update_loop.start()
        if not self.music_check_loop.is_running():
            self.music_check_loop.start()
        if not self.update_status_loop.is_running():
            self.update_status_loop.start()
        if not self.check_new_releases_loop.is_running():
            self.check_new_releases_loop.start()
        if not self.weekly_recap_loop.is_running():
            self.weekly_recap_loop.start()
    
    async def auto_follow_top_artists(self):
        """Suit automatiquement les 10 artistes préférés"""
        top_artists = self.db.get_top_artists(10)
        
        for artist_name, _ in top_artists:
            # Recherche l'ID de l'artiste via l'API Spotify
            artist_id = await self.get_artist_id(artist_name)
            if artist_id:
                self.db.add_followed_artist(artist_id, artist_name)
        
        print(f"✅ Suivi automatique de {len(top_artists)} artistes configuré")
    
    async def get_artist_id(self, artist_name):
        """Récupère l'ID Spotify d'un artiste"""
        try:
            headers = self.get_spotify_headers()
            url = f"https://api.spotify.com/v1/search?q={artist_name}&type=artist&limit=1"
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data['artists']['items']:
                    return data['artists']['items'][0]['id']
        except Exception as e:
            print(f"⚠️ Erreur recherche artiste: {e}")
        return None
    
    def refresh_spotify_token(self):
        """Rafraîchit le token Spotify"""
        try:
            auth_url = "https://accounts.spotify.com/api/token"
            auth_str = f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}"
            auth_b64 = base64.b64encode(auth_str.encode()).decode()
            
            headers = {
                "Authorization": f"Basic {auth_b64}",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            data = {
                "grant_type": "refresh_token",
                "refresh_token": SPOTIFY_REFRESH_TOKEN
            }
            
            response = requests.post(auth_url, headers=headers, data=data, timeout=10)
            
            if response.status_code == 200:
                self.spotify_access_token = response.json()['access_token']
                return True
            return False
        except Exception as e:
            print(f"⚠️ Erreur refresh Spotify: {e}")
            return False
    
    def get_spotify_headers(self):
        """Obtient les headers Spotify"""
        if not self.spotify_access_token:
            self.refresh_spotify_token()
        return {"Authorization": f"Bearer {self.spotify_access_token}"}
    
    def get_current_track_full(self):
        """Récupère la track en cours"""
        try:
            headers = self.get_spotify_headers()
            url = "https://api.spotify.com/v1/me/player/currently-playing"
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 401:
                self.refresh_spotify_token()
                headers = self.get_spotify_headers()
                response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200 and response.text:
                data = response.json()
                if data and 'item' in data:
                    return data
            return None
        except Exception as e:
            print(f"⚠️ Erreur current track: {e}")
            return None
    
    async def get_artist_genres(self, artist_id):
        """Récupère les genres d'un artiste"""
        try:
            headers = self.get_spotify_headers()
            url = f"https://api.spotify.com/v1/artists/{artist_id}"
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('genres', [])
        except Exception as e:
            print(f"⚠️ Erreur genres: {e}")
        return []
    
    async def get_track_audio_features(self, track_id):
        """Récupère les audio features d'une track"""
        try:
            headers = self.get_spotify_headers()
            url = f"https://api.spotify.com/v1/audio-features/{track_id}"
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"⚠️ Erreur audio features: {e}")
        return None
    
    async def check_music_change(self):
        """Vérifie les changements de musique"""
        try:
            current_data = self.get_current_track_full()
            
            if not current_data or 'item' not in current_data:
                return
            
            track = current_data['item']
            track_id = track['id']
            
            if track_id != self.last_track_id:
                self.last_track_id = track_id
                self.current_track_data = track
                
                # Récupère genres et audio features
                artist_id = track['artists'][0]['id']
                genres = await self.get_artist_genres(artist_id)
                audio_features = await self.get_track_audio_features(track_id)
                
                # Enregistre avec enrichissement
                self.db.save_spotify_play(track, genres, audio_features)
                
                # Notification
                channel_id = self.db.get_config('MUSIC_CHANNEL_ID')
                if channel_id:
                    channel = self.get_channel(int(channel_id))
                    if channel:
                        await self.send_music_notification(channel, track, genres)
                        print(f"🎵 Nouvelle musique: {track['artists'][0]['name']} - {track['name']}")
        
        except Exception as e:
            print(f"⚠️ Erreur check music: {e}")
    
    async def send_music_notification(self, channel, track, genres=None):
        """Envoie une notification de musique"""
        try:
            artist = track['artists'][0]['name']
            title = track['name']
            album = track['album']['name']
            image_url = track['album']['images'][0]['url'] if track['album']['images'] else None
            spotify_url = track['external_urls']['spotify']
            duration_ms = track['duration_ms']
            duration_min = duration_ms // 60000
            duration_sec = (duration_ms % 60000) // 1000
            
            play_count = self.db.get_track_play_count(track_id=track['id'])
            
            emoji = self.theme_manager.get_emoji('music')
            color = self.theme_manager.get_color('primary')
            
            embed = discord.Embed(
                title=f"{emoji} Nouvelle musique en cours",
                description=f"**[{title}]({spotify_url})**",
                color=color,
                timestamp=datetime.now()
            )
            
            embed.add_field(name="🎤 Artiste", value=artist, inline=True)
            embed.add_field(name="💿 Album", value=album, inline=True)
            embed.add_field(name="⏱️ Durée", value=f"{duration_min}:{duration_sec:02d}", inline=True)
            embed.add_field(name="🔢 Écoutes", value=f"{play_count} fois", inline=True)
            
            if genres:
                genres_str = ', '.join(genres[:3])
                embed.add_field(name="🎸 Genres", value=genres_str, inline=True)
            
            if image_url:
                embed.set_thumbnail(url=image_url)
            
            embed.set_footer(text="Spotify Tracker", icon_url="https://i.imgur.com/vw8N4fy.png")
            
            await channel.send(embed=embed)
        
        except Exception as e:
            print(f"⚠️ Erreur notification: {e}")
    
    async def check_new_releases(self):
        """Vérifie les nouvelles sorties des artistes suivis"""
        try:
            followed = self.db.get_followed_artists()
            
            for artist_id, artist_name in followed:
                # Récupère les derniers albums
                headers = self.get_spotify_headers()
                url = f"https://api.spotify.com/v1/artists/{artist_id}/albums?limit=5"
                response = requests.get(url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    albums = response.json()['items']
                    
                    for album in albums:
                        release_date = album['release_date']
                        # Vérifie si sorti il y a moins de 7 jours
                        try:
                            release_datetime = datetime.strptime(release_date, '%Y-%m-%d')
                            days_ago = (datetime.now() - release_datetime).days
                            
                            if days_ago <= 7:
                                # Nouvelle sortie !
                                is_new = self.db.save_new_release(
                                    artist_id, artist_name, 
                                    album['id'], album['name'], 
                                    release_date
                                )
                                
                                if is_new:
                                    await self.notify_new_release(artist_name, album)
                        except:
                            pass
        
        except Exception as e:
            print(f"⚠️ Erreur check releases: {e}")
    
    async def notify_new_release(self, artist_name, album):
        """Notifie une nouvelle sortie"""
        try:
            channel_id = self.db.get_config('MUSIC_CHANNEL_ID')
            if not channel_id:
                return
            
            channel = self.get_channel(int(channel_id))
            if not channel:
                return
            
            emoji = self.theme_manager.get_emoji('party')
            color = self.theme_manager.get_color('success')
            
            embed = discord.Embed(
                title=f"{emoji} Nouvelle Sortie !",
                description=f"**{artist_name}** vient de sortir quelque chose de nouveau !",
                color=color,
                timestamp=datetime.now()
            )
            
            embed.add_field(name="💿 Album/Single", value=album['name'], inline=False)
            embed.add_field(name="📅 Date", value=album['release_date'], inline=True)
            embed.add_field(name="🔗 Lien", value=f"[Écouter sur Spotify]({album['external_urls']['spotify']})", inline=True)
            
            if album.get('images'):
                embed.set_thumbnail(url=album['images'][0]['url'])
            
            embed.set_footer(text="Suivi des artistes 🔔")
            
            await channel.send(f"🎉 @everyone Nouvelle sortie de **{artist_name}** !", embed=embed)
            print(f"🎉 Nouvelle sortie notifiée: {artist_name} - {album['name']}")
        
        except Exception as e:
            print(f"⚠️ Erreur notif release: {e}")
    
    async def send_weekly_recap(self):
        """Envoie le récap hebdomadaire"""
        try:
            channel_id = self.db.get_config('MUSIC_CHANNEL_ID')
            if not channel_id:
                return
            
            channel = self.get_channel(int(channel_id))
            if not channel:
                return
            
            emoji = self.theme_manager.get_emoji('party')
            color = self.theme_manager.get_color('primary')
            
            # Stats de la semaine
            total_plays = self.db.get_track_play_count()
            total_time = self.db.get_total_listening_time(days=7)
            top_tracks = self.db.get_top_tracks(3, days=7)
            top_artists = self.db.get_top_artists(3, days=7)
            top_genres = self.db.get_top_genres(3, days=7)
            discoveries = self.db.get_new_discoveries(days=7)
            current_streak, best_streak = self.analytics.calculate_streaks()
            
            embed = discord.Embed(
                title=f"{emoji} Votre Semaine en Musique",
                description="Récapitulatif de vos 7 derniers jours d'écoute",
                color=color,
                timestamp=datetime.now()
            )
            
            # Temps d'écoute
            hours = total_time // 60
            minutes = total_time % 60
            embed.add_field(
                name="⏱️ Temps d'écoute",
                value=f"**{hours}h {minutes}m**",
                inline=True
            )
            
            # Streak
            embed.add_field(
                name=f"{self.theme_manager.get_emoji('fire')} Streak",
                value=f"**{current_streak} jours**",
                inline=True
            )
            
            # Découvertes
            embed.add_field(
                name="🆕 Découvertes",
                value=f"**{len(discoveries)}** nouvelles musiques",
                inline=True
            )
            
            # Top Track
            if top_tracks:
                track = top_tracks[0]
                embed.add_field(
                    name=f"{self.theme_manager.get_emoji('trophy')} Top Track",
                    value=f"**{track[0]}**\n*{track[1]}* • {track[2]} écoutes",
                    inline=False
                )
            
            # Top Artiste
            if top_artists:
                artist = top_artists[0]
                embed.add_field(
                    name="🎤 Top Artiste",
                    value=f"**{artist[0]}** • {artist[1]} écoutes",
                    inline=True
                )
            
            # Top Genre
            if top_genres:
                genre = top_genres[0]
                embed.add_field(
                    name="🎸 Top Genre",
                    value=f"**{genre[0]}** • {genre[1]} écoutes",
                    inline=True
                )
            
            embed.set_footer(text="Récap hebdomadaire automatique 📊")
            
            await channel.send("📬 **Votre récap de la semaine est arrivé !**", embed=embed)
            
            # Génère et envoie le graphique
            graph = self.analytics.generate_listening_trend(7)
            if graph:
                file = discord.File(graph, filename="weekly_trend.png")
                graph_embed = discord.Embed(
                    title="📈 Évolution de la semaine",
                    color=color
                )
                graph_embed.set_image(url="attachment://weekly_trend.png")
                await channel.send(embed=graph_embed, file=file)
            
            # Heatmap
            heatmap = self.analytics.generate_activity_heatmap()
            if heatmap:
                file = discord.File(heatmap, filename="heatmap.png")
                heatmap_embed = discord.Embed(
                    title="🔥 Vos horaires d'écoute",
                    color=color
                )
                heatmap_embed.set_image(url="attachment://heatmap.png")
                await channel.send(embed=heatmap_embed, file=file)
            
            print("✅ Récap hebdomadaire envoyé")
        
        except Exception as e:
            print(f"⚠️ Erreur récap hebdo: {e}")
    
    def get_github_repos(self):
        """Récupère les repos GitHub"""
        try:
            headers = {
                "Authorization": f"token {GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3+json"
            }
            url = f"https://api.github.com/users/{GITHUB_USERNAME}/repos?per_page=100"
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                repos = response.json()
                self.github_repos_count = len(repos)
                return repos
            return []
        except Exception as e:
            print(f"⚠️ Erreur repos GitHub: {e}")
            return []
    
    def get_github_events(self):
        """Récupère les événements GitHub"""
        try:
            headers = {
                "Authorization": f"token {GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3+json"
            }
            url = f"https://api.github.com/users/{GITHUB_USERNAME}/events?per_page=100"
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            return []
        except Exception as e:
            print(f"⚠️ Erreur events GitHub: {e}")
            return []
    
    async def check_github_updates(self):
        """Vérifie les nouveaux pushes GitHub"""
        try:
            events = self.get_github_events()
            
            for event in events:
                if event['type'] == 'PushEvent':
                    is_new = self.db.save_github_push(event)
                    
                    if is_new:
                        channel_id = self.db.get_config('GIT_CHANNEL_ID')
                        if channel_id:
                            channel = self.get_channel(int(channel_id))
                            if channel:
                                await self.send_github_notification(channel, event)
        
        except Exception as e:
            print(f"⚠️ Erreur check GitHub: {e}")
    
    async def send_github_notification(self, channel, event):
        """Envoie une notification de push GitHub"""
        try:
            repo_name = event['repo']['name']
            branch = event['payload'].get('ref', 'unknown').replace('refs/heads/', '')
            commits = event['payload'].get('commits', [])
            
            color = self.theme_manager.get_color('secondary')
            
            embed = discord.Embed(
                title=f"🔧 Nouveau Push sur {repo_name}",
                color=color,
                timestamp=datetime.now()
            )
            
            embed.add_field(name="📂 Repository", value=repo_name, inline=True)
            embed.add_field(name="🌿 Branch", value=branch, inline=True)
            embed.add_field(name="📝 Commits", value=str(len(commits)), inline=True)
            
            if commits:
                commits_text = ""
                for commit in commits[:5]:
                    msg = commit['message'].split('\n')[0][:50]
                    commits_text += f"• {msg}\n"
                
                embed.add_field(name="💬 Messages", value=commits_text, inline=False)
            
            repo_url = f"https://github.com/{repo_name}"
            embed.add_field(name="🔗 Lien", value=f"[Voir le repository]({repo_url})", inline=False)
            
            embed.set_footer(text="GitHub Tracker")
            
            await channel.send(embed=embed)
        
        except Exception as e:
            print(f"⚠️ Erreur notification GitHub: {e}")
    
    async def update_data(self):
        """Met à jour toutes les données"""
        print(f"\n🔄 Mise à jour... ({datetime.now().strftime('%H:%M:%S')})")
        
        self.get_github_repos()
        await self.check_github_updates()
        
        print("✅ Mise à jour terminée")
    
    async def update_bot_status(self):
        """Met à jour le statut du bot"""
        try:
            total_pushes = self.db.get_total_pushes()
            
            current_track = self.get_current_track_full()
            if current_track and 'item' in current_track:
                track = current_track['item']
                status_text = f"{track['artists'][0]['name']} - {track['name']}"
            else:
                status_text = f"{self.github_repos_count} repos • {total_pushes} pushes"
            
            await self.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.listening,
                    name=status_text
                )
            )
        
        except Exception as e:
            print(f"⚠️ Erreur status: {e}")
    
    @tasks.loop(minutes=5)
    async def update_loop(self):
        """Boucle de mise à jour GitHub"""
        await self.update_data()
    
    @tasks.loop(seconds=30)
    async def music_check_loop(self):
        """Boucle de vérification musique"""
        await self.check_music_change()
    
    @tasks.loop(minutes=2)
    async def update_status_loop(self):
        """Boucle de mise à jour du statut"""
        await self.update_bot_status()
    
    @tasks.loop(hours=2)
    async def check_new_releases_loop(self):
        """Boucle de vérification des nouvelles sorties"""
        await self.check_new_releases()
    
    @tasks.loop(time=time(hour=20, minute=0))
    async def weekly_recap_loop(self):
        """Boucle du récap hebdomadaire (Dimanche 20h)"""
        if datetime.now().weekday() == 6:  # Dimanche = 6
            await self.send_weekly_recap()
    
    @update_loop.before_loop
    async def before_update_loop(self):
        await self.wait_until_ready()
    
    @music_check_loop.before_loop
    async def before_music_check_loop(self):
        await self.wait_until_ready()
    
    @update_status_loop.before_loop
    async def before_status_loop(self):
        await self.wait_until_ready()
    
    @check_new_releases_loop.before_loop
    async def before_releases_loop(self):
        await self.wait_until_ready()
    
    @weekly_recap_loop.before_loop
    async def before_weekly_recap(self):
        await self.wait_until_ready()

# ========== COMMANDES ==========

@commands.command(name='theme')
async def theme(ctx, theme_name: str = None):
    """Change ou affiche le thème
    Thèmes disponibles: violet, ocean, sunset, forest
    Usage: !theme [nom]
    """
    if not theme_name:
        current = ctx.bot.db.get_config('theme', 'violet')
        themes_list = ', '.join(THEMES.keys())
        
        embed = discord.Embed(
            title="🎨 Thèmes Disponibles",
            description=f"Thème actuel: **{current}**",
            color=ctx.bot.theme_manager.get_color('primary')
        )
        
        embed.add_field(
            name="Thèmes",
            value=themes_list,
            inline=False
        )
        
        embed.add_field(
            name="Utilisation",
            value="`!theme [nom]`\nExemple: `!theme ocean`",
            inline=False
        )
        
        await ctx.send(embed=embed)
    else:
        if ctx.bot.theme_manager.set_theme(theme_name):
            await ctx.send(f"✅ Thème changé: **{theme_name}**")
        else:
            themes_list = ', '.join(THEMES.keys())
            await ctx.send(f"❌ Thème invalide. Disponibles: {themes_list}")

@commands.command(name='setspotify')
@commands.has_permissions(administrator=True)
async def setspotify(ctx):
    """Définit le canal pour les notifications Spotify"""
    ctx.bot.db.save_config('MUSIC_CHANNEL_ID', ctx.channel.id)
    await ctx.send(f"✅ Canal Spotify défini : {ctx.channel.mention}")

@commands.command(name='setgit')
@commands.has_permissions(administrator=True)
async def setgit(ctx):
    """Définit le canal pour les notifications GitHub"""
    ctx.bot.db.save_config('GIT_CHANNEL_ID', ctx.channel.id)
    await ctx.send(f"✅ Canal GitHub défini : {ctx.channel.mention}")

@commands.command(name='follow')
async def follow(ctx, *, artist_name: str):
    """Suit un artiste pour les nouvelles sorties
    Usage: !follow [nom artiste]
    """
    await ctx.send(f"🔍 Recherche de {artist_name}...")
    
    artist_id = await ctx.bot.get_artist_id(artist_name)
    
    if artist_id:
        ctx.bot.db.add_followed_artist(artist_id, artist_name)
        
        emoji = ctx.bot.theme_manager.get_emoji('star')
        color = ctx.bot.theme_manager.get_color('success')
        
        embed = discord.Embed(
            title=f"{emoji} Artiste suivi !",
            description=f"Vous suivez maintenant **{artist_name}**",
            color=color
        )
        embed.add_field(
            name="🔔 Notifications",
            value="Vous serez averti de toutes les nouvelles sorties !",
            inline=False
        )
        await ctx.send(embed=embed)
    else:
        await ctx.send(f"❌ Artiste '{artist_name}' non trouvé")

@commands.command(name='following')
async def following(ctx):
    """Liste les artistes suivis"""
    followed = ctx.bot.db.get_followed_artists()
    
    if not followed:
        await ctx.send("❌ Vous ne suivez aucun artiste pour le moment")
        return
    
    color = ctx.bot.theme_manager.get_color('primary')
    
    embed = discord.Embed(
        title="🔔 Artistes Suivis",
        description=f"Vous suivez {len(followed)} artiste(s)",
        color=color
    )
    
    artists_text = "\n".join([f"• {name}" for _, name in followed])
    embed.add_field(name="Liste", value=artists_text, inline=False)
    
    await ctx.send(embed=embed)

@commands.command(name='genres')
async def genres(ctx, days: int = 30):
    """Affiche vos genres préférés
    Usage: !genres [jours]
    """
    await ctx.send(f"🎸 Analyse de vos genres ({days} jours)...")
    
    top_genres = ctx.bot.db.get_top_genres(10, days)
    
    if not top_genres:
        await ctx.send("❌ Pas de données de genres disponibles")
        return
    
    color = ctx.bot.theme_manager.get_color('primary')
    
    embed = discord.Embed(
        title=f"🎸 Top Genres ({days} jours)",
        color=color,
        timestamp=datetime.now()
    )
    
    genres_text = ""
    for i, (genre, count) in enumerate(top_genres, 1):
        genres_text += f"**{i}.** {genre} • {count} écoutes\n"
    
    embed.add_field(name="📊 Classement", value=genres_text, inline=False)
    
    await ctx.send(embed=embed)
    
    # Génère le camembert
    graph = ctx.bot.analytics.generate_genre_pie(8, days)
    if graph:
        file = discord.File(graph, filename="genres.png")
        graph_embed = discord.Embed(
            title="📊 Distribution des genres",
            color=color
        )
        graph_embed.set_image(url="attachment://genres.png")
        await ctx.send(embed=graph_embed, file=file)

@commands.command(name='trend')
async def trend(ctx, days: int = 30):
    """Affiche le graphique d'évolution des écoutes
    Usage: !trend [jours]
    """
    await ctx.send(f"📊 Génération du graphique ({days} jours)...")
    
    graph = ctx.bot.analytics.generate_listening_trend(days)
    
    if not graph:
        await ctx.send("❌ Pas assez de données pour générer le graphique")
        return
    
    file = discord.File(graph, filename="trend.png")
    
    color = ctx.bot.theme_manager.get_color('primary')
    embed = discord.Embed(
        title=f"📈 Évolution des écoutes ({days} jours)",
        color=color,
        timestamp=datetime.now()
    )
    embed.set_image(url="attachment://trend.png")
    
    await ctx.send(embed=embed, file=file)

@commands.command(name='heatmap')
async def heatmap(ctx):
    """Affiche la heatmap d'activité musicale"""
    await ctx.send("🔥 Génération de la heatmap...")
    
    graph = ctx.bot.analytics.generate_activity_heatmap()
    
    if not graph:
        await ctx.send("❌ Pas assez de données")
        return
    
    file = discord.File(graph, filename="heatmap.png")
    
    color = ctx.bot.theme_manager.get_color('accent')
    embed = discord.Embed(
        title="🔥 Heatmap d'activité",
        description="Vos heures et jours d'écoute préférés",
        color=color,
        timestamp=datetime.now()
    )
    embed.set_image(url="attachment://heatmap.png")
    
    await ctx.send(embed=embed, file=file)

# Suite et fin du fichier bot.py (partie patterns et commandes restantes)

# ... (tout le code précédent reste identique) ...

@commands.command(name='patterns')
async def patterns(ctx):
    """Analyse vos patterns d'écoute"""
    await ctx.send("🔍 Analyse de vos habitudes...")
    
    patterns_data = ctx.bot.analytics.analyze_listening_patterns()
    
    color = ctx.bot.theme_manager.get_color('primary')
    
    embed = discord.Embed(
        title="🎯 Vos Patterns d'Écoute",
        description="Artistes préférés par moment de la journée",
        color=color,
        timestamp=datetime.now()
    )
    
    period_emojis = {
        'Matin': '🌅',
        'Après-midi': '☀️',
        'Soirée': '🌆',
        'Nuit': '🌙'
    }
    
    for period in ['Matin', 'Après-midi', 'Soirée', 'Nuit']:
        if period in patterns_data:
            artist, count = patterns_data[period]
            emoji = period_emojis[period]
            embed.add_field(
                name=f"{emoji} {period}",
                value=f"**{artist}**\n{count} écoutes",
                inline=True
            )
    
    await ctx.send(embed=embed)

@commands.command(name='streak')
async def streak(ctx):
    """Affiche vos streaks d'écoute"""
    current, best = ctx.bot.analytics.calculate_streaks()
    
    emoji = ctx.bot.theme_manager.get_emoji('fire')
    color = ctx.bot.theme_manager.get_color('warning')
    
    embed = discord.Embed(
        title=f"{emoji} Vos Streaks d'Écoute",
        color=color,
        timestamp=datetime.now()
    )
    
    embed.add_field(
        name="⚡ Streak Actuel",
        value=f"**{current} jours** consécutifs",
        inline=True
    )
    
    embed.add_field(
        name=f"{ctx.bot.theme_manager.get_emoji('trophy')} Meilleur Streak",
        value=f"**{best} jours** consécutifs",
        inline=True
    )
    
    if current >= 7:
        embed.set_footer(text="🎉 Incroyable ! Continuez comme ça !")
    elif current >= 3:
        embed.set_footer(text="👍 Vous êtes régulier !")
    else:
        embed.set_footer(text="💪 N'oubliez pas d'écouter de la musique !")
    
    await ctx.send(embed=embed)

@commands.command(name='wrapped')
async def wrapped(ctx, periode: str = 'mois'):
    """Récap style Spotify Wrapped
    Usage: !wrapped [mois/année/semaine]
    """
    await ctx.send(f"🎁 Génération de votre Wrapped {periode}...")
    
    db = ctx.bot.db
    analytics = ctx.bot.analytics
    
    # Détermine la période
    if periode.lower() in ['semaine', 'week']:
        days = 7
        title = "🎁 Votre Wrapped de la Semaine"
    elif periode.lower() in ['mois', 'month']:
        days = 30
        title = "🎁 Votre Wrapped du Mois"
    else:
        days = 365
        title = "🎁 Votre Wrapped de l'Année"
    
    # Stats globales
    total_time = db.get_total_listening_time(days=days)
    top_tracks = db.get_top_tracks(3, days=days)
    top_artists = db.get_top_artists(3, days=days)
    top_genres = db.get_top_genres(3, days=days)
    discoveries = db.get_new_discoveries(days=days)
    current_streak, best_streak = analytics.calculate_streaks()
    
    emoji = ctx.bot.theme_manager.get_emoji('party')
    color = ctx.bot.theme_manager.get_color('primary')
    
    embed = discord.Embed(
        title=title,
        description=f"Vos stats des {days} derniers jours",
        color=color,
        timestamp=datetime.now()
    )
    
    # Temps d'écoute
    hours = total_time // 60
    minutes = total_time % 60
    embed.add_field(
        name="⏱️ Temps d'écoute",
        value=f"**{hours}h {minutes}m**",
        inline=True
    )
    
    # Streak
    embed.add_field(
        name=f"{ctx.bot.theme_manager.get_emoji('fire')} Meilleur Streak",
        value=f"**{best_streak} jours**",
        inline=True
    )
    
    # Découvertes
    embed.add_field(
        name="🆕 Découvertes",
        value=f"**{len(discoveries)}** nouvelles musiques",
        inline=True
    )
    
    # Top Track
    if top_tracks:
        track = top_tracks[0]
        embed.add_field(
            name=f"{ctx.bot.theme_manager.get_emoji('trophy')} Top Track",
            value=f"**{track[0]}**\n*{track[1]}* • {track[2]} écoutes",
            inline=False
        )
    
    # Top Artiste
    if top_artists:
        artist = top_artists[0]
        embed.add_field(
            name="🎤 Top Artiste",
            value=f"**{artist[0]}** • {artist[1]} écoutes",
            inline=True
        )
    
    # Top Genre
    if top_genres:
        genre = top_genres[0]
        embed.add_field(
            name="🎸 Top Genre",
            value=f"**{genre[0]}** • {genre[1]} écoutes",
            inline=True
        )
    
    embed.set_footer(text=f"🎉 Merci d'avoir écouté avec nous ! {emoji}")
    
    await ctx.send(embed=embed)
    
    # Génère le graphique
    graph = analytics.generate_listening_trend(days)
    if graph:
        file = discord.File(graph, filename="wrapped.png")
        await ctx.send(file=file)

@commands.command(name='mood')
async def mood(ctx):
    """Analyse le mood de vos écoutes récentes"""
    mood_data = ctx.bot.analytics.get_mood_analysis()
    
    if not mood_data:
        await ctx.send("❌ Pas assez de données pour analyser le mood")
        return
    
    color = ctx.bot.theme_manager.get_color('primary')
    
    embed = discord.Embed(
        title="😊 Analyse de Mood",
        description=f"Votre mood cette semaine: **{mood_data['mood']}**",
        color=color,
        timestamp=datetime.now()
    )
    
    # Barres de progression
    valence_bar = "█" * int(mood_data['valence'] * 10) + "░" * (10 - int(mood_data['valence'] * 10))
    energy_bar = "█" * int(mood_data['energy'] * 10) + "░" * (10 - int(mood_data['energy'] * 10))
    dance_bar = "█" * int(mood_data['danceability'] * 10) + "░" * (10 - int(mood_data['danceability'] * 10))
    
    embed.add_field(
        name="😊 Positivité",
        value=f"`{valence_bar}` {mood_data['valence']:.1%}",
        inline=False
    )
    
    embed.add_field(
        name="⚡ Énergie",
        value=f"`{energy_bar}` {mood_data['energy']:.1%}",
        inline=False
    )
    
    embed.add_field(
        name="💃 Dansabilité",
        value=f"`{dance_bar}` {mood_data['danceability']:.1%}",
        inline=False
    )
    
    await ctx.send(embed=embed)

@commands.command(name='recap')
async def recap(ctx, service: str = 'spotify'):
    """Affiche un récapitulatif complet
    Services: spotify, git
    """
    if service.lower() == 'spotify':
        await recap_spotify(ctx)
    elif service.lower() == 'git':
        await recap_git(ctx)
    else:
        await ctx.send("❌ Service invalide. Utilisez: `spotify` ou `git`")

async def recap_spotify(ctx):
    """Récapitulatif Spotify complet"""
    await ctx.send("🔄 Génération du récapitulatif Spotify...")
    
    db = ctx.bot.db
    color = ctx.bot.theme_manager.get_color('primary')
    
    # Statistiques
    total_plays = db.get_track_play_count()
    total_time_minutes = db.get_total_listening_time()
    total_hours = total_time_minutes / 60
    total_days = total_hours / 24
    
    top_tracks = db.get_top_tracks(10)
    top_artists = db.get_top_artists(10)
    top_genres = db.get_top_genres(5)
    
    # Création de l'embed
    embed = discord.Embed(
        title="🎵 Récapitulatif Spotify Complet",
        description="Toutes vos statistiques d'écoute",
        color=color,
        timestamp=datetime.now()
    )
    
    # Temps d'écoute
    embed.add_field(
        name="⏱️ Temps d'écoute total",
        value=f"**{total_hours:.1f} heures** ({total_days:.2f} jours)\n"
              f"📊 {total_plays} écoutes au total",
        inline=False
    )
    
    # Top Tracks
    if top_tracks:
        tracks_text = ""
        for i, (name, artist, count, _, _) in enumerate(top_tracks[:5], 1):
            tracks_text += f"**{i}.** {name} - *{artist}*\n└ {count} écoutes\n"
        
        embed.add_field(
            name="🎵 Top 5 Titres",
            value=tracks_text,
            inline=False
        )
    
    # Top Artists
    if top_artists:
        artists_text = ""
        for i, (artist, count) in enumerate(top_artists[:5], 1):
            artists_text += f"**{i}.** {artist} - {count} écoutes\n"
        
        embed.add_field(
            name="🎤 Top 5 Artistes",
            value=artists_text,
            inline=False
        )
    
    # Top Genres
    if top_genres:
        genres_text = ""
        for i, (genre, count) in enumerate(top_genres, 1):
            genres_text += f"**{i}.** {genre} - {count} écoutes\n"
        
        embed.add_field(
            name="🎸 Top 5 Genres",
            value=genres_text,
            inline=False
        )
    
    # Musique actuelle
    current = ctx.bot.get_current_track_full()
    if current and 'item' in current:
        track = current['item']
        embed.add_field(
            name="🎧 En cours d'écoute",
            value=f"**{track['artists'][0]['name']} - {track['name']}**",
            inline=False
        )
        if track['album']['images']:
            embed.set_thumbnail(url=track['album']['images'][0]['url'])
    
    embed.set_footer(text="Spotify Tracker", icon_url="https://i.imgur.com/vw8N4fy.png")
    
    await ctx.send(embed=embed)

async def recap_git(ctx):
    """Récapitulatif GitHub complet"""
    await ctx.send("🔄 Génération du récapitulatif GitHub...")
    
    db = ctx.bot.db
    color = ctx.bot.theme_manager.get_color('secondary')
    
    # Statistiques
    total_pushes = db.get_total_pushes()
    recent_pushes = db.get_recent_pushes(10)
    repos = ctx.bot.get_github_repos()
    
    embed = discord.Embed(
        title="🔧 Récapitulatif GitHub Complet",
        description="Toutes vos statistiques de développement",
        color=color,
        timestamp=datetime.now()
    )
    
    # Statistiques générales
    embed.add_field(
        name="📊 Statistiques",
        value=f"**{len(repos)} repositories**\n"
              f"**{total_pushes} pushes** enregistrés",
        inline=False
    )
    
    # Derniers pushes
    if recent_pushes:
        pushes_text = ""
        for repo, date, commits, _, branch in recent_pushes[:5]:
            date_obj = datetime.strptime(date, '%Y-%m-%dT%H:%M:%SZ')
            date_formatted = date_obj.strftime('%d/%m à %H:%M')
            pushes_text += f"**{repo}** ({branch})\n└ {date_formatted} • {commits} commit(s)\n"
        
        embed.add_field(
            name="🔄 Derniers Pushes",
            value=pushes_text,
            inline=False
        )
    
    # Repos actifs
    if repos:
        repos_sorted = sorted(repos, key=lambda x: x.get('updated_at', ''), reverse=True)
        repos_text = ""
        for repo in repos_sorted[:5]:
            name = repo['name']
            lang = repo.get('language', 'N/A')
            repos_text += f"• **{name}** ({lang})\n"
        
        embed.add_field(
            name="📂 Repositories Récents",
            value=repos_text,
            inline=False
        )
    
    embed.set_footer(text="GitHub Tracker")
    
    await ctx.send(embed=embed)

@commands.command(name='listen')
async def listen(ctx):
    """Affiche la musique en cours"""
    current = ctx.bot.get_current_track_full()
    
    if not current or 'item' not in current:
        await ctx.send("❌ Aucune musique en cours")
        return
    
    track = current['item']
    artist_id = track['artists'][0]['id']
    genres = await ctx.bot.get_artist_genres(artist_id)
    await ctx.bot.send_music_notification(ctx.channel, track, genres)

@commands.command(name='search')
async def search(ctx, *, query: str):
    """Recherche une musique ou un artiste
    Usage: !search [nom]
    """
    await ctx.send(f"🔍 Recherche de '{query}'...")
    
    db = ctx.bot.db
    results = db.search_track(query)
    
    if not results:
        await ctx.send(f"❌ Aucun résultat pour '{query}'")
        return
    
    color = ctx.bot.theme_manager.get_color('accent')
    
    embed = discord.Embed(
        title=f"🔍 Résultats pour '{query}'",
        color=color,
        timestamp=datetime.now()
    )
    
    for track_name, artist, count, _, image, first_play, genres in results[:5]:
        date_obj = datetime.strptime(first_play, '%Y-%m-%d %H:%M:%S')
        date_formatted = date_obj.strftime('%d/%m/%Y')
        
        value_text = f"🎤 {artist}\n🔢 {count} écoutes\n📅 Découvert le {date_formatted}"
        
        if genres:
            genres_list = genres.split(',')[:2]
            value_text += f"\n🎸 {', '.join(genres_list)}"
        
        embed.add_field(
            name=f"🎵 {track_name}",
            value=value_text,
            inline=False
        )
    
    if results and results[0][4]:
        embed.set_thumbnail(url=results[0][4])
    
    embed.set_footer(text=f"{len(results)} résultat(s) trouvé(s)")
    
    await ctx.send(embed=embed)

@commands.command(name='new')
async def new(ctx, temps: str = '7'):
    """Liste les nouvelles découvertes
    Usage: !new [jours]
    Exemple: !new 7 (derniers 7 jours)
    """
    try:
        days = int(temps)
    except ValueError:
        await ctx.send("❌ Durée invalide. Utilisez un nombre de jours.")
        return
    
    await ctx.send(f"🔍 Recherche des découvertes des {days} derniers jours...")
    
    db = ctx.bot.db
    discoveries = db.get_new_discoveries(days)
    
    if not discoveries:
        await ctx.send(f"❌ Aucune nouvelle découverte ces {days} derniers jours")
        return
    
    color = ctx.bot.theme_manager.get_color('warning')
    
    embed = discord.Embed(
        title=f"🆕 Nouvelles découvertes ({days} derniers jours)",
        description=f"{len(discoveries)} nouvelles musiques !",
        color=color,
        timestamp=datetime.now()
    )
    
    for track, artist, first_play, count in discoveries[:10]:
        date_obj = datetime.strptime(first_play, '%Y-%m-%d %H:%M:%S')
        date_formatted = date_obj.strftime('%d/%m à %H:%M')
        
        embed.add_field(
            name=f"🎵 {track}",
            value=f"🎤 {artist}\n"
                  f"📅 {date_formatted}\n"
                  f"🔢 {count} écoute(s)",
            inline=True
        )
    
    if len(discoveries) > 10:
        embed.set_footer(text=f"Affichage de 10 sur {len(discoveries)} découvertes")
    
    await ctx.send(embed=embed)

@commands.command(name='stats')
async def stats(ctx):
    """Affiche les statistiques rapides"""
    db = ctx.bot.db
    color = ctx.bot.theme_manager.get_color('primary')
    
    # Stats Spotify
    total_plays = db.get_track_play_count()
    total_time = db.get_total_listening_time()
    top_artist = db.get_top_artists(1)
    
    # Stats GitHub
    total_pushes = db.get_total_pushes()
    repos_count = ctx.bot.github_repos_count
    
    embed = discord.Embed(
        title="📊 Statistiques Rapides",
        color=color,
        timestamp=datetime.now()
    )
    
    # Spotify
    spotify_text = f"🎵 **{total_plays}** écoutes\n"
    spotify_text += f"⏱️ **{total_time // 60}h{total_time % 60}m** d'écoute\n"
    if top_artist:
        spotify_text += f"🎤 Top: **{top_artist[0][0]}**"
    
    embed.add_field(
        name="🎵 Spotify",
        value=spotify_text,
        inline=True
    )
    
    # GitHub
    github_text = f"📂 **{repos_count}** repositories\n"
    github_text += f"🔄 **{total_pushes}** pushes"
    
    embed.add_field(
        name="🔧 GitHub",
        value=github_text,
        inline=True
    )
    
    await ctx.send(embed=embed)

@commands.command(name='top')
async def top(ctx, categorie: str = 'tracks', limite: int = 10):
    """Affiche le top des écoutes
    Usage: !top [tracks/artists/genres] [nombre]
    Exemple: !top tracks 5
    """
    db = ctx.bot.db
    color = ctx.bot.theme_manager.get_color('warning')
    
    if categorie.lower() in ['tracks', 'track', 'titres', 'titre']:
        results = db.get_top_tracks(limite)
        
        embed = discord.Embed(
            title=f"🏆 Top {len(results)} Titres",
            color=color,
            timestamp=datetime.now()
        )
        
        for i, (name, artist, count, _, image) in enumerate(results, 1):
            embed.add_field(
                name=f"{i}. {name}",
                value=f"🎤 {artist}\n🔢 {count} écoutes",
                inline=False
            )
        
        if results and results[0][4]:
            embed.set_thumbnail(url=results[0][4])
    
    elif categorie.lower() in ['artists', 'artist', 'artistes', 'artiste']:
        results = db.get_top_artists(limite)
        
        embed = discord.Embed(
            title=f"🏆 Top {len(results)} Artistes",
            color=color,
            timestamp=datetime.now()
        )
        
        for i, (artist, count) in enumerate(results, 1):
            embed.add_field(
                name=f"{i}. {artist}",
                value=f"🔢 {count} écoutes",
                inline=True
            )
    
    elif categorie.lower() in ['genres', 'genre']:
        results = db.get_top_genres(limite)
        
        embed = discord.Embed(
            title=f"🏆 Top {len(results)} Genres",
            color=color,
            timestamp=datetime.now()
        )
        
        for i, (genre, count) in enumerate(results, 1):
            embed.add_field(
                name=f"{i}. {genre}",
                value=f"🔢 {count} écoutes",
                inline=True
            )
    
    else:
        await ctx.send("❌ Catégorie invalide. Utilisez `tracks`, `artists` ou `genres`")
        return
    
    embed.set_footer(text="Spotify Tracker")
    await ctx.send(embed=embed)

@commands.command(name='update')
async def update(ctx):
    """Force une mise à jour manuelle"""
    await ctx.send("🔄 Mise à jour forcée en cours...")
    await ctx.bot.update_data()
    await ctx.send("✅ Mise à jour terminée !")

@commands.command(name='help')
async def help_command(ctx):
    """Affiche toutes les commandes disponibles"""
    color = ctx.bot.theme_manager.get_color('primary')
    
    embed = discord.Embed(
        title="📚 Commandes Disponibles",
        description="Liste complète des commandes du bot",
        color=color
    )
    
    # Configuration
    embed.add_field(
        name="⚙️ Configuration (Admin)",
        value=(
            "`!setspotify` - Définir le canal Spotify\n"
            "`!setgit` - Définir le canal GitHub\n"
            "`!update` - Forcer une mise à jour\n"
            "`!theme [nom]` - Changer le thème"
        ),
        inline=False
    )
    
    # Spotify
    embed.add_field(
        name="🎵 Spotify",
        value=(
            "`!listen` - Musique en cours\n"
            "`!recap spotify` - Récapitulatif complet\n"
            "`!search <nom>` - Rechercher une musique/artiste\n"
            "`!new <jours>` - Nouvelles découvertes\n"
            "`!top [tracks/artists/genres] [nombre]` - Top écoutes\n"
            "`!genres [jours]` - Top genres\n"
            "`!trend [jours]` - Graphique d'évolution\n"
            "`!heatmap` - Carte de chaleur d'activité\n"
            "`!patterns` - Patterns d'écoute\n"
            "`!streak` - Streaks d'écoute\n"
            "`!mood` - Analyse de mood\n"
            "`!wrapped [période]` - Spotify Wrapped"
        ),
        inline=False
    )
    
    # Artistes
    embed.add_field(
        name="🔔 Suivi d'Artistes",
        value=(
            "`!follow <artiste>` - Suivre un artiste\n"
            "`!following` - Liste des artistes suivis"
        ),
        inline=False
    )
    
    # GitHub
    embed.add_field(
        name="🔧 GitHub",
        value=(
            "`!recap git` - Récapitulatif complet"
        ),
        inline=False
    )
    
    # Général
    embed.add_field(
        name="📊 Général",
        value=(
            "`!stats` - Statistiques rapides\n"
            "`!help` - Afficher cette aide"
        ),
        inline=False
    )
    
    embed.set_footer(text="🤖 Bot Spotify & GitHub Tracker v3.0")
    
    await ctx.send(embed=embed)

# Fonction de vérification de configuration
def check_config():
    """Vérifie la configuration"""
    missing = []
    
    required_vars = {
        'DISCORD_TOKEN': DISCORD_TOKEN,
        'GITHUB_TOKEN': GITHUB_TOKEN,
        'GITHUB_USERNAME': GITHUB_USERNAME,
        'SPOTIFY_CLIENT_ID': SPOTIFY_CLIENT_ID,
        'SPOTIFY_CLIENT_SECRET': SPOTIFY_CLIENT_SECRET,
        'SPOTIFY_REFRESH_TOKEN': SPOTIFY_REFRESH_TOKEN
    }
    
    for var_name, var_value in required_vars.items():
        if not var_value:
            missing.append(var_name)
    
    if missing:
        print("\n❌ Variables manquantes dans .env:")
        for var in missing:
            print(f"   - {var}")
        print("\nVeuillez remplir le fichier .env\n")
        return False
    
    print("\n✅ Configuration valide")
    return True

# Point d'entrée
if __name__ == "__main__":
    print("\n" + "="*60)
    print("🤖 BOT DISCORD - SPOTIFY & GITHUB TRACKER v3.0")
    print("="*60 + "\n")
    
    if not check_config():
        exit(1)
    
    print("🚀 Démarrage du bot...\n")
    
    # Crée le bot
    bot = ProfileUpdater()
    
    # Ajoute les commandes
    bot.add_command(theme)
    bot.add_command(setspotify)
    bot.add_command(setgit)
    bot.add_command(follow)
    bot.add_command(following)
    bot.add_command(genres)
    bot.add_command(trend)
    bot.add_command(heatmap)
    bot.add_command(patterns)
    bot.add_command(streak)
    bot.add_command(wrapped)
    bot.add_command(mood)
    bot.add_command(recap)
    bot.add_command(listen)
    bot.add_command(search)
    bot.add_command(new)
    bot.add_command(stats)
    bot.add_command(top)
    bot.add_command(update)
    bot.add_command(help_command)
    
    try:
        bot.run(DISCORD_TOKEN)
    except KeyboardInterrupt:
        print("\n\n👋 Arrêt du bot...")
    except discord.LoginFailure:
        print("\n❌ Token Discord invalide")
    except Exception as e:
        print(f"\n❌ Erreur: {e}")