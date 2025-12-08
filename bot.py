import discord
from discord.ext import commands, tasks
import requests
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import base64
import sqlite3
import json
from collections import Counter

# Charge les variables d'environnement
load_dotenv()

# Configuration
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
GITHUB_USERNAME = os.getenv('GITHUB_USERNAME')
SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
SPOTIFY_REFRESH_TOKEN = os.getenv('SPOTIFY_REFRESH_TOKEN')

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
        
        # Table pour les écoutes Spotify
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS spotify_plays (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                track_id TEXT NOT NULL,
                track_name TEXT NOT NULL,
                artist_name TEXT NOT NULL,
                album_name TEXT,
                duration_ms INTEGER,
                played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                image_url TEXT
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
        
        conn.commit()
        conn.close()
    
    def save_spotify_play(self, track_data):
        """Enregistre une écoute Spotify"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO spotify_plays 
            (track_id, track_name, artist_name, album_name, duration_ms, image_url)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            track_data['id'],
            track_data['name'],
            track_data['artists'][0]['name'],
            track_data['album']['name'],
            track_data['duration_ms'],
            track_data['album']['images'][0]['url'] if track_data['album']['images'] else None
        ))
        
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
    
    def get_top_tracks(self, limit=10):
        """Récupère les tracks les plus écoutées"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT track_name, artist_name, COUNT(*) as play_count, track_id, image_url
            FROM spotify_plays
            GROUP BY track_id
            ORDER BY play_count DESC
            LIMIT ?
        ''', (limit,))
        
        results = cursor.fetchall()
        conn.close()
        return results
    
    def get_top_artists(self, limit=10):
        """Récupère les artistes les plus écoutés"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT artist_name, COUNT(*) as play_count
            FROM spotify_plays
            GROUP BY artist_name
            ORDER BY play_count DESC
            LIMIT ?
        ''', (limit,))
        
        results = cursor.fetchall()
        conn.close()
        return results
    
    def get_total_listening_time(self):
        """Calcule le temps d'écoute total"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT SUM(duration_ms) FROM spotify_plays')
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
            return False  # Push déjà enregistré
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
                   track_id, image_url, MIN(played_at) as first_play
            FROM spotify_plays
            WHERE track_name LIKE ? OR artist_name LIKE ?
            GROUP BY track_id
            ORDER BY play_count DESC
        ''', (f'%{query}%', f'%{query}%'))
        
        results = cursor.fetchall()
        conn.close()
        return results

class ProfileUpdater(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.presences = True
        intents.guilds = True
        super().__init__(command_prefix='!', intents=intents)
        
        self.db = Database()
        self.spotify_access_token = None
        self.last_track_id = None
        self.current_track_data = None
        self.github_repos_count = 0
        
    async def on_ready(self):
        print("\n" + "="*60)
        print(f"✅ Bot connecté: {self.user}")
        print(f"📊 ID: {self.user.id}")
        print("="*60)
        
        # Première mise à jour
        await self.update_data()
        
        # Démarre les boucles
        if not self.update_loop.is_running():
            self.update_loop.start()
        if not self.music_check_loop.is_running():
            self.music_check_loop.start()
        if not self.update_status_loop.is_running():
            self.update_status_loop.start()
    
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
    
    async def check_music_change(self):
        """Vérifie les changements de musique"""
        try:
            current_data = self.get_current_track_full()
            
            if not current_data or 'item' not in current_data:
                return
            
            track = current_data['item']
            track_id = track['id']
            
            # Nouvelle musique détectée
            if track_id != self.last_track_id:
                self.last_track_id = track_id
                self.current_track_data = track
                
                # Enregistre dans la base de données
                self.db.save_spotify_play(track)
                
                # Envoie notification
                channel_id = self.db.get_config('MUSIC_CHANNEL_ID')
                if channel_id:
                    channel = self.get_channel(int(channel_id))
                    if channel:
                        await self.send_music_notification(channel, track)
                        print(f"🎵 Nouvelle musique: {track['artists'][0]['name']} - {track['name']}")
        
        except Exception as e:
            print(f"⚠️ Erreur check music: {e}")
    
    async def send_music_notification(self, channel, track):
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
            
            # Compte les écoutes
            play_count = self.db.get_track_play_count(track_id=track['id'])
            
            embed = discord.Embed(
                title="🎵 Nouvelle musique en cours",
                description=f"**[{title}]({spotify_url})**",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            
            embed.add_field(name="🎤 Artiste", value=artist, inline=True)
            embed.add_field(name="💿 Album", value=album, inline=True)
            embed.add_field(name="⏱️ Durée", value=f"{duration_min}:{duration_sec:02d}", inline=True)
            embed.add_field(name="🔢 Écoutes", value=f"{play_count} fois", inline=True)
            
            if image_url:
                embed.set_thumbnail(url=image_url)
            
            embed.set_footer(text="Spotify Tracker", icon_url="https://i.imgur.com/vw8N4fy.png")
            
            await channel.send(embed=embed)
        
        except Exception as e:
            print(f"⚠️ Erreur notification: {e}")
    
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
                    # Tente d'enregistrer le push
                    is_new = self.db.save_github_push(event)
                    
                    if is_new:
                        # Nouveau push détecté
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
            
            embed = discord.Embed(
                title=f"🔧 Nouveau Push sur {repo_name}",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            embed.add_field(name="📂 Repository", value=repo_name, inline=True)
            embed.add_field(name="🌿 Branch", value=branch, inline=True)
            embed.add_field(name="📝 Commits", value=str(len(commits)), inline=True)
            
            # Détails des commits
            if commits:
                commits_text = ""
                for commit in commits[:5]:  # Max 5 commits
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
        
        # Met à jour les repos
        self.get_github_repos()
        
        # Vérifie les nouveaux pushes
        await self.check_github_updates()
        
        print("✅ Mise à jour terminée")
    
    async def update_bot_status(self):
        """Met à jour le statut du bot"""
        try:
            # Récupère les statistiques
            total_pushes = self.db.get_total_pushes()
            
            # Musique actuelle
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
    
    @update_loop.before_loop
    async def before_update_loop(self):
        await self.wait_until_ready()
    
    @music_check_loop.before_loop
    async def before_music_check_loop(self):
        await self.wait_until_ready()
    
    @update_status_loop.before_loop
    async def before_status_loop(self):
        await self.wait_until_ready()

# ========== COMMANDES ==========

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
    
    # Statistiques
    total_plays = db.get_track_play_count()
    total_time_minutes = db.get_total_listening_time()
    total_hours = total_time_minutes / 60
    total_days = total_hours / 24
    
    top_tracks = db.get_top_tracks(10)
    top_artists = db.get_top_artists(10)
    
    # Création de l'embed
    embed = discord.Embed(
        title="🎵 Récapitulatif Spotify Complet",
        description="Toutes vos statistiques d'écoute",
        color=discord.Color.green(),
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
    
    # Statistiques
    total_pushes = db.get_total_pushes()
    recent_pushes = db.get_recent_pushes(10)
    repos = ctx.bot.get_github_repos()
    
    embed = discord.Embed(
        title="🔧 Récapitulatif GitHub Complet",
        description="Toutes vos statistiques de développement",
        color=discord.Color.blue(),
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
    await ctx.bot.send_music_notification(ctx.channel, track)

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
    
    embed = discord.Embed(
        title=f"🔍 Résultats pour '{query}'",
        color=discord.Color.purple(),
        timestamp=datetime.now()
    )
    
    for track_name, artist, count, _, image, first_play in results[:5]:
        date_obj = datetime.strptime(first_play, '%Y-%m-%d %H:%M:%S')
        date_formatted = date_obj.strftime('%d/%m/%Y')
        
        embed.add_field(
            name=f"🎵 {track_name}",
            value=f"🎤 {artist}\n"
                  f"🔢 {count} écoutes\n"
                  f"📅 Découvert le {date_formatted}",
            inline=False
        )
    
    if results and results[0][4]:  # Image du premier résultat
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
    
    embed = discord.Embed(
        title=f"🆕 Nouvelles découvertes ({days} derniers jours)",
        description=f"{len(discoveries)} nouvelles musiques !",
        color=discord.Color.gold(),
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
    
    # Stats Spotify
    total_plays = db.get_track_play_count()
    total_time = db.get_total_listening_time()
    top_artist = db.get_top_artists(1)
    
    # Stats GitHub
    total_pushes = db.get_total_pushes()
    repos_count = ctx.bot.github_repos_count
    
    embed = discord.Embed(
        title="📊 Statistiques Rapides",
        color=discord.Color.blurple(),
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
    Usage: !top [tracks/artists] [nombre]
    Exemple: !top tracks 5
    """
    db = ctx.bot.db
    
    if categorie.lower() in ['tracks', 'track', 'titres', 'titre']:
        results = db.get_top_tracks(limite)
        
        embed = discord.Embed(
            title=f"🏆 Top {len(results)} Titres",
            color=discord.Color.gold(),
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
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )
        
        for i, (artist, count) in enumerate(results, 1):
            embed.add_field(
                name=f"{i}. {artist}",
                value=f"🔢 {count} écoutes",
                inline=True
            )
    
    else:
        await ctx.send("❌ Catégorie invalide. Utilisez `tracks` ou `artists`")
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
    embed = discord.Embed(
        title="📚 Commandes Disponibles",
        description="Liste complète des commandes du bot",
        color=discord.Color.blue()
    )
    
    # Configuration
    embed.add_field(
        name="⚙️ Configuration (Admin)",
        value=(
            "`!setspotify` - Définir le canal Spotify\n"
            "`!setgit` - Définir le canal GitHub\n"
            "`!update` - Forcer une mise à jour"
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
            "`!top [tracks/artists] [nombre]` - Top écoutes"
        ),
        inline=False
    )
    
    # GitHub
    embed.add_field(
        name="🔧 GitHub",
        value=(
            "`!recap git` - Récapitulatif complet\n"
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
    
    embed.set_footer(text="🤖 Bot Spotify & GitHub Tracker")
    
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
    print("🤖 BOT DISCORD - SPOTIFY & GITHUB TRACKER v2.0")
    print("="*60 + "\n")
    
    if not check_config():
        exit(1)
    
    print("🚀 Démarrage du bot...\n")
    
    # Crée le bot
    bot = ProfileUpdater()
    
    # Ajoute les commandes
    bot.add_command(setspotify)
    bot.add_command(setgit)
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