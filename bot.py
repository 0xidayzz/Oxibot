import discord
from discord.ext import commands, tasks
from discord import app_commands
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

load_dotenv()

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
SPOTIFY_REFRESH_TOKEN = os.getenv('SPOTIFY_REFRESH_TOKEN')

THEMES = {
    'violet': {'primary': 0x9B59B6, 'secondary': 0xBB8FCE, 'accent': 0xE8DAEF, 'success': 0x52BE80, 'warning': 0xF39C12, 'error': 0xE74C3C, 'emojis': {'music': '🎵', 'fire': '🔥', 'star': '⭐', 'trophy': '🏆', 'party': '🎉', 'rocket': '🚀'}},
    'ocean': {'primary': 0x3498DB, 'secondary': 0x5DADE2, 'accent': 0xAED6F1, 'success': 0x1ABC9C, 'warning': 0xF39C12, 'error': 0xE74C3C, 'emojis': {'music': '🌊', 'fire': '💙', 'star': '✨', 'trophy': '🏅', 'party': '🎊', 'rocket': '⚡'}},
    'sunset': {'primary': 0xFF6B6B, 'secondary': 0xFFE66D, 'accent': 0xFF8E53, 'success': 0x4ECDC4, 'warning': 0xF39C12, 'error': 0xE74C3C, 'emojis': {'music': '🌅', 'fire': '🔥', 'star': '🌟', 'trophy': '🏆', 'party': '🎈', 'rocket': '🚀'}},
    'forest': {'primary': 0x27AE60, 'secondary': 0x52BE80, 'accent': 0xA9DFBF, 'success': 0x58D68D, 'warning': 0xF39C12, 'error': 0xE74C3C, 'emojis': {'music': '🍃', 'fire': '🌿', 'star': '⭐', 'trophy': '🏆', 'party': '🌳', 'rocket': '🚀'}}
}

class ThemeManager:
    def __init__(self, db):
        self.db = db
        self.current_theme = self.load_theme()
    
    def load_theme(self):
        theme_name = self.db.get_config('theme', 'violet')
        return THEMES.get(theme_name, THEMES['violet'])
    
    def set_theme(self, theme_name):
        if theme_name.lower() in THEMES:
            self.db.save_config('theme', theme_name.lower())
            self.current_theme = THEMES[theme_name.lower()]
            return True
        return False
    
    def get_color(self, color_type='primary'):
        return self.current_theme.get(color_type, 0x9B59B6)
    
    def get_emoji(self, emoji_type):
        return self.current_theme['emojis'].get(emoji_type, '🎵')

# VOIR LE FICHIER SUIVANT POUR LA SUITE (database.py et analytics.py à créer séparément)
# Ce fichier contient seulement la structure principale

class Database:
    """Classe Database - voir document 1 pour l'implémentation complète"""
    def __init__(self, db_name='bot_data.db'):
        self.db_name = db_name
        self.init_database()
    
    def get_connection(self):
        return sqlite3.connect(self.db_name)
    
    def init_database(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''CREATE TABLE IF NOT EXISTS spotify_plays (
            id INTEGER PRIMARY KEY AUTOINCREMENT, track_id TEXT NOT NULL, track_name TEXT NOT NULL,
            artist_name TEXT NOT NULL, album_name TEXT, duration_ms INTEGER,
            played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, image_url TEXT, genres TEXT,
            artist_id TEXT, popularity INTEGER, valence REAL, energy REAL, danceability REAL)''')
        
        cursor.execute('''CREATE TABLE IF NOT EXISTS followed_artists (
            artist_id TEXT PRIMARY KEY, artist_name TEXT NOT NULL,
            last_check TIMESTAMP, last_release_id TEXT)''')
        
        cursor.execute('''CREATE TABLE IF NOT EXISTS new_releases (
            id INTEGER PRIMARY KEY AUTOINCREMENT, artist_id TEXT NOT NULL,
            artist_name TEXT NOT NULL, album_id TEXT NOT NULL, album_name TEXT NOT NULL,
            release_date TEXT, detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, notified INTEGER DEFAULT 0)''')
        
        cursor.execute('''CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT NOT NULL)''')
        
        conn.commit()
        conn.close()
    
    # Méthodes save_spotify_play, add/remove_followed_artist, get_top_tracks/artists/genres, etc.
    # Voir document 1 pour l'implémentation complète de toutes les méthodes
    
    def save_config(self, key, value):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)', (key, str(value)))
        conn.commit()
        conn.close()
    
    def get_config(self, key, default=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT value FROM config WHERE key = ?', (key,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else default

class BotAnalytics:
    """Classe Analytics - voir document 2 pour l'implémentation complète"""
    def __init__(self, db, theme_manager):
        self.db = db
        self.theme = theme_manager
        plt.style.use('dark_background')
    
    # Méthodes generate_listening_trend, generate_activity_heatmap, generate_genre_pie, etc.
    # Voir document 2 pour l'implémentation complète

class SpotifyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.presences = True
        intents.guilds = True
        super().__init__(command_prefix=['!', '/'], intents=intents)
        
        self.db = Database()
        self.theme_manager = ThemeManager(self.db)
        self.analytics = BotAnalytics(self.db, self.theme_manager)
        self.spotify_access_token = None
        self.last_track_id = None
        
    async def setup_hook(self):
        await self.tree.sync()
        
    async def on_ready(self):
        print(f"\n{'='*60}\n✅ Bot connecté: {self.user}\n📊 ID: {self.user.id}\n🎨 Thème: {self.db.get_config('theme', 'violet')}\n{'='*60}\n")
        
        await self.auto_follow_top_artists()
        await self.update_bot_description()
        
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
        top_artists = self.db.get_top_artists(10)
        for artist_name, _ in top_artists:
            artist_id = await self.get_artist_id(artist_name)
            if artist_id:
                self.db.add_followed_artist(artist_id, artist_name)
        print(f"✅ Suivi automatique de {len(top_artists)} artistes configuré")
    
    async def get_artist_id(self, artist_name):
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
        try:
            auth_url = "https://accounts.spotify.com/api/token"
            auth_str = f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}"
            auth_b64 = base64.b64encode(auth_str.encode()).decode()
            
            headers = {"Authorization": f"Basic {auth_b64}", "Content-Type": "application/x-www-form-urlencoded"}
            data = {"grant_type": "refresh_token", "refresh_token": SPOTIFY_REFRESH_TOKEN}
            
            response = requests.post(auth_url, headers=headers, data=data, timeout=10)
            if response.status_code == 200:
                self.spotify_access_token = response.json()['access_token']
                return True
            return False
        except Exception as e:
            print(f"⚠️ Erreur refresh Spotify: {e}")
            return False
    
    def get_spotify_headers(self):
        if not self.spotify_access_token:
            self.refresh_spotify_token()
        return {"Authorization": f"Bearer {self.spotify_access_token}"}
    
    def get_current_track_full(self):
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
    
    async def update_bot_description(self):
        """Met à jour la description du bot avec les stats"""
        try:
            total_time = self.db.get_total_listening_time()
            hours = total_time // 60
            top_artist = self.db.get_top_artists(1)
            top_track = self.db.get_top_tracks(1)
            
            description = f"⏱️ {hours}h d'écoute"
            if top_artist:
                description += f" | 🎤 {top_artist[0][0]}"
            if top_track:
                description += f" | 🎵 {top_track[0][0]}"
            
            await self.user.edit(bio=description[:190])  # Limite Discord
        except Exception as e:
            print(f"⚠️ Erreur MAJ description: {e}")
    
    async def check_music_change(self):
        try:
            current_data = self.get_current_track_full()
            if not current_data or 'item' not in current_data:
                return
            
            track = current_data['item']
            track_id = track['id']
            
            if track_id != self.last_track_id:
                self.last_track_id = track_id
                
                artist_id = track['artists'][0]['id']
                genres = await self.get_artist_genres(artist_id)
                audio_features = await self.get_track_audio_features(track_id)
                
                self.db.save_spotify_play(track, genres, audio_features)
                
                channel_id = self.db.get_config('MUSIC_CHANNEL_ID')
                if channel_id:
                    channel = self.get_channel(int(channel_id))
                    if channel:
                        await self.send_music_notification(channel, track, genres)
                        print(f"🎵 Nouvelle musique: {track['artists'][0]['name']} - {track['name']}")
        except Exception as e:
            print(f"⚠️ Erreur check music: {e}")
    
    async def get_artist_genres(self, artist_id):
        try:
            headers = self.get_spotify_headers()
            url = f"https://api.spotify.com/v1/artists/{artist_id}"
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                return response.json().get('genres', [])
        except Exception as e:
            print(f"⚠️ Erreur genres: {e}")
        return []
    
    async def get_track_audio_features(self, track_id):
        try:
            headers = self.get_spotify_headers()
            url = f"https://api.spotify.com/v1/audio-features/{track_id}"
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"⚠️ Erreur audio features: {e}")
        return None
    
    async def send_music_notification(self, channel, track, genres=None):
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
            
            embed = discord.Embed(title=f"{emoji} Nouvelle musique en cours", description=f"**[{title}]({spotify_url})**", color=color, timestamp=datetime.now())
            embed.add_field(name="🎤 Artiste", value=artist, inline=True)
            embed.add_field(name="💿 Album", value=album, inline=True)
            embed.add_field(name="⏱️ Durée", value=f"{duration_min}:{duration_sec:02d}", inline=True)
            embed.add_field(name="🔢 Écoutes", value=f"{play_count} fois", inline=True)
            
            if genres:
                embed.add_field(name="🎸 Genres", value=', '.join(genres[:3]), inline=True)
            
            if image_url:
                embed.set_thumbnail(url=image_url)
            
            embed.set_footer(text="Spotify Tracker", icon_url="https://i.imgur.com/vw8N4fy.png")
            await channel.send(embed=embed)
        except Exception as e:
            print(f"⚠️ Erreur notification: {e}")
    
    async def check_new_releases(self):
        try:
            followed = self.db.get_followed_artists()
            for artist_id, artist_name in followed:
                headers = self.get_spotify_headers()
                url = f"https://api.spotify.com/v1/artists/{artist_id}/albums?limit=5"
                response = requests.get(url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    albums = response.json()['items']
                    for album in albums:
                        release_date = album['release_date']
                        try:
                            release_datetime = datetime.strptime(release_date, '%Y-%m-%d')
                            days_ago = (datetime.now() - release_datetime).days
                            if days_ago <= 7:
                                is_new = self.db.save_new_release(artist_id, artist_name, album['id'], album['name'], release_date)
                                if is_new:
                                    await self.notify_new_release(artist_name, album)
                        except:
                            pass
        except Exception as e:
            print(f"⚠️ Erreur check releases: {e}")
    
    async def notify_new_release(self, artist_name, album):
        try:
            channel_id = self.db.get_config('NOTIFICATIONS_CHANNEL_ID')
            if not channel_id:
                return
            channel = self.get_channel(int(channel_id))
            if not channel:
                return
            
            emoji = self.theme_manager.get_emoji('party')
            color = self.theme_manager.get_color('success')
            
            embed = discord.Embed(title=f"{emoji} Nouvelle Sortie !", description=f"**{artist_name}** vient de sortir quelque chose de nouveau !", color=color, timestamp=datetime.now())
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
        try:
            channel_id = self.db.get_config('NOTIFICATIONS_CHANNEL_ID')
            if not channel_id:
                return
            channel = self.get_channel(int(channel_id))
            if not channel:
                return
            
            emoji = self.theme_manager.get_emoji('party')
            color = self.theme_manager.get_color('primary')
            
            total_time = self.db.get_total_listening_time(days=7)
            top_tracks = self.db.get_top_tracks(3, days=7)
            top_artists = self.db.get_top_artists(3, days=7)
            top_genres = self.db.get_top_genres(3, days=7)
            discoveries = self.db.get_new_discoveries(days=7)
            current_streak, best_streak = self.analytics.calculate_streaks()
            
            embed = discord.Embed(title=f"{emoji} Votre Semaine en Musique", description="Récapitulatif de vos 7 derniers jours d'écoute", color=color, timestamp=datetime.now())
            
            hours = total_time // 60
            minutes = total_time % 60
            embed.add_field(name="⏱️ Temps d'écoute", value=f"**{hours}h {minutes}m**", inline=True)
            embed.add_field(name=f"{self.theme_manager.get_emoji('fire')} Streak", value=f"**{current_streak} jours**", inline=True)
            embed.add_field(name="🆕 Découvertes", value=f"**{len(discoveries)}** nouvelles musiques", inline=True)
            
            if top_tracks:
                track = top_tracks[0]
                embed.add_field(name=f"{self.theme_manager.get_emoji('trophy')} Top Track", value=f"**{track[0]}**\n*{track[1]}* • {track[2]} écoutes", inline=False)
            
            if top_artists:
                embed.add_field(name="🎤 Top Artiste", value=f"**{top_artists[0][0]}** • {top_artists[0][1]} écoutes", inline=True)
            
            if top_genres:
                embed.add_field(name="🎸 Top Genre", value=f"**{top_genres[0][0]}** • {top_genres[0][1]} écoutes", inline=True)
            
            embed.set_footer(text="Récap hebdomadaire automatique 📊")
            await channel.send("📬 **Votre récap de la semaine est arrivé !**", embed=embed)
            
            graph = self.analytics.generate_listening_trend(7)
            if graph:
                file = discord.File(graph, filename="weekly_trend.png")
                graph_embed = discord.Embed(title="📈 Évolution de la semaine", color=color)
                graph_embed.set_image(url="attachment://weekly_trend.png")
                await channel.send(embed=graph_embed, file=file)
            
            heatmap = self.analytics.generate_activity_heatmap()
            if heatmap:
                file = discord.File(heatmap, filename="heatmap.png")
                heatmap_embed = discord.Embed(title="🔥 Vos horaires d'écoute", color=color)
                heatmap_embed.set_image(url="attachment://heatmap.png")
                await channel.send(embed=heatmap_embed, file=file)
            
            print("✅ Récap hebdomadaire envoyé")
        except Exception as e:
            print(f"⚠️ Erreur récap hebdo: {e}")
    
    async def update_bot_status(self):
        try:
            current_track = self.get_current_track_full()
            if current_track and 'item' in current_track:
                track = current_track['item']
                status_text = f"{track['artists'][0]['name']} - {track['name']}"
            else:
                total_time = self.db.get_total_listening_time()
                hours = total_time // 60
                status_text = f"{hours}h d'écoute"
            
            await self.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name=status_text))
        except Exception as e:
            print(f"⚠️ Erreur status: {e}")
    
    @tasks.loop(seconds=30)
    async def music_check_loop(self):
        await self.check_music_change()
    
    @tasks.loop(minutes=2)
    async def update_status_loop(self):
        await self.update_bot_status()
    
    @tasks.loop(hours=2)
    async def check_new_releases_loop(self):
        await self.check_new_releases()
    
    @tasks.loop(time=time(hour=20, minute=0))
    async def weekly_recap_loop(self):
        if datetime.now().weekday() == 6:
            await self.send_weekly_recap()
    
    @tasks.loop(hours=24)
    async def update_loop(self):
        await self.update_bot_description()
    
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

# SUITE DU FICHIER bot.py - COMMANDES SLASH ET PREFIX

# Importer le bot depuis le fichier principal
# from main import SpotifyBot, discord, commands, app_commands, datetime

# ========== COMMANDES SLASH (/commandes) ==========

@bot.tree.command(name="setchannel", description="Définit le canal pour toutes les notifications")
@app_commands.describe(type_notif="Type de notifications (music/all)")
async def setchannel_slash(interaction: discord.Interaction, type_notif: str = "all"):
    """Définit le canal pour les notifications"""
    if type_notif.lower() in ["all", "toutes", "tout"]:
        bot.db.save_config('NOTIFICATIONS_CHANNEL_ID', interaction.channel.id)
        await interaction.response.send_message(f"✅ Toutes les notifications seront envoyées dans {interaction.channel.mention}")
    elif type_notif.lower() in ["music", "musique"]:
        bot.db.save_config('MUSIC_CHANNEL_ID', interaction.channel.id)
        await interaction.response.send_message(f"✅ Notifications musicales activées dans {interaction.channel.mention}")
    else:
        await interaction.response.send_message("❌ Type invalide. Utilisez `all` ou `music`")

@bot.tree.command(name="theme", description="Change le thème du bot")
@app_commands.describe(nom="Nom du thème (violet/ocean/sunset/forest)")
async def theme_slash(interaction: discord.Interaction, nom: str = None):
    """Change ou affiche le thème"""
    if not nom:
        current = bot.db.get_config('theme', 'violet')
        themes_list = ', '.join(THEMES.keys())
        
        embed = discord.Embed(
            title="🎨 Thèmes Disponibles",
            description=f"**Thème actuel:** {current}",
            color=bot.theme_manager.get_color('primary')
        )
        embed.add_field(name="Thèmes", value=themes_list, inline=False)
        embed.add_field(name="Utilisation", value="`/theme nom:[violet/ocean/sunset/forest]`", inline=False)
        
        await interaction.response.send_message(embed=embed)
    else:
        if bot.theme_manager.set_theme(nom):
            await interaction.response.send_message(f"✅ Thème changé: **{nom}**")
        else:
            themes_list = ', '.join(THEMES.keys())
            await interaction.response.send_message(f"❌ Thème invalide. Disponibles: {themes_list}")

@bot.tree.command(name="follow", description="Suit un artiste pour les nouvelles sorties")
@app_commands.describe(artiste="Nom de l'artiste à suivre")
async def follow_slash(interaction: discord.Interaction, artiste: str):
    """Suit un artiste"""
    await interaction.response.send_message(f"🔍 Recherche de {artiste}...")
    
    artist_id = await bot.get_artist_id(artiste)
    
    if artist_id:
        bot.db.add_followed_artist(artist_id, artiste)
        
        emoji = bot.theme_manager.get_emoji('star')
        color = bot.theme_manager.get_color('success')
        
        embed = discord.Embed(
            title=f"{emoji} Artiste suivi !",
            description=f"Vous suivez maintenant **{artiste}**",
            color=color
        )
        embed.add_field(name="🔔 Notifications", value="Vous serez averti de toutes les nouvelles sorties !", inline=False)
        await interaction.edit_original_response(content=None, embed=embed)
    else:
        await interaction.edit_original_response(content=f"❌ Artiste '{artiste}' non trouvé")

@bot.tree.command(name="unfollow", description="Arrête de suivre un artiste")
@app_commands.describe(artiste="Nom de l'artiste à ne plus suivre")
async def unfollow_slash(interaction: discord.Interaction, artiste: str):
    """Arrête de suivre un artiste"""
    if bot.db.remove_followed_artist(artiste):
        await interaction.response.send_message(f"✅ Vous ne suivez plus **{artiste}**")
    else:
        await interaction.response.send_message(f"❌ Artiste '{artiste}' non trouvé dans vos suivis")

@bot.tree.command(name="following", description="Liste les artistes suivis")
async def following_slash(interaction: discord.Interaction):
    """Liste les artistes suivis"""
    followed = bot.db.get_followed_artists()
    
    if not followed:
        await interaction.response.send_message("❌ Vous ne suivez aucun artiste pour le moment")
        return
    
    color = bot.theme_manager.get_color('primary')
    
    embed = discord.Embed(
        title="🔔 Artistes Suivis",
        description=f"Vous suivez {len(followed)} artiste(s)",
        color=color
    )
    
    artists_text = "\n".join([f"• {name}" for _, name in followed])
    embed.add_field(name="Liste", value=artists_text, inline=False)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="genres", description="Affiche vos genres préférés")
@app_commands.describe(jours="Nombre de jours à analyser (défaut: 30)")
async def genres_slash(interaction: discord.Interaction, jours: int = 30):
    """Affiche vos genres préférés"""
    await interaction.response.send_message(f"🎸 Analyse de vos genres ({jours} jours)...")
    
    top_genres = bot.db.get_top_genres(10, jours)
    
    if not top_genres:
        await interaction.edit_original_response(content="❌ Pas de données de genres disponibles")
        return
    
    color = bot.theme_manager.get_color('primary')
    
    embed = discord.Embed(
        title=f"🎸 Top Genres ({jours} jours)",
        color=color,
        timestamp=datetime.now()
    )
    
    genres_text = "\n".join([f"**{i}.** {genre} • {count} écoutes" for i, (genre, count) in enumerate(top_genres, 1)])
    embed.add_field(name="📊 Classement", value=genres_text, inline=False)
    
    await interaction.edit_original_response(content=None, embed=embed)
    
    # Génère le camembert
    graph = bot.analytics.generate_genre_pie(8, jours)
    if graph:
        file = discord.File(graph, filename="genres.png")
        graph_embed = discord.Embed(title="📊 Distribution des genres", color=color)
        graph_embed.set_image(url="attachment://genres.png")
        await interaction.followup.send(embed=graph_embed, file=file)

@bot.tree.command(name="mood", description="Analyse le mood de vos écoutes récentes")
async def mood_slash(interaction: discord.Interaction):
    """Analyse le mood"""
    mood_data = bot.analytics.get_mood_analysis()
    
    if not mood_data:
        await interaction.response.send_message("❌ Pas assez de données pour analyser le mood")
        return
    
    color = bot.theme_manager.get_color('primary')
    
    embed = discord.Embed(
        title="😊 Analyse de Mood",
        description=f"Votre mood cette semaine: **{mood_data['mood']}**",
        color=color,
        timestamp=datetime.now()
    )
    
    valence_bar = "█" * int(mood_data['valence'] * 10) + "░" * (10 - int(mood_data['valence'] * 10))
    energy_bar = "█" * int(mood_data['energy'] * 10) + "░" * (10 - int(mood_data['energy'] * 10))
    dance_bar = "█" * int(mood_data['danceability'] * 10) + "░" * (10 - int(mood_data['danceability'] * 10))
    
    embed.add_field(name="😊 Positivité", value=f"`{valence_bar}` {mood_data['valence']:.1%}", inline=False)
    embed.add_field(name="⚡ Énergie", value=f"`{energy_bar}` {mood_data['energy']:.1%}", inline=False)
    embed.add_field(name="💃 Dansabilité", value=f"`{dance_bar}` {mood_data['danceability']:.1%}", inline=False)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="wrapped", description="Récap style Spotify Wrapped")
@app_commands.describe(periode="Période à analyser (semaine/mois/annee)")
async def wrapped_slash(interaction: discord.Interaction, periode: str = "mois"):
    """Récap style Spotify Wrapped"""
    await interaction.response.send_message(f"🎁 Génération de votre Wrapped {periode}...")
    
    if periode.lower() in ['semaine', 'week']:
        days, title = 7, "🎁 Votre Wrapped de la Semaine"
    elif periode.lower() in ['mois', 'month']:
        days, title = 30, "🎁 Votre Wrapped du Mois"
    else:
        days, title = 365, "🎁 Votre Wrapped de l'Année"
    
    total_time = bot.db.get_total_listening_time(days=days)
    top_tracks = bot.db.get_top_tracks(3, days=days)
    top_artists = bot.db.get_top_artists(3, days=days)
    top_genres = bot.db.get_top_genres(3, days=days)
    discoveries = bot.db.get_new_discoveries(days=days)
    current_streak, best_streak = bot.analytics.calculate_streaks()
    
    emoji = bot.theme_manager.get_emoji('party')
    color = bot.theme_manager.get_color('primary')
    
    embed = discord.Embed(title=title, description=f"Vos stats des {days} derniers jours", color=color, timestamp=datetime.now())
    
    hours, minutes = total_time // 60, total_time % 60
    embed.add_field(name="⏱️ Temps d'écoute", value=f"**{hours}h {minutes}m**", inline=True)
    embed.add_field(name=f"{bot.theme_manager.get_emoji('fire')} Meilleur Streak", value=f"**{best_streak} jours**", inline=True)
    embed.add_field(name="🆕 Découvertes", value=f"**{len(discoveries)}** nouvelles musiques", inline=True)
    
    if top_tracks:
        track = top_tracks[0]
        embed.add_field(name=f"{bot.theme_manager.get_emoji('trophy')} Top Track", value=f"**{track[0]}**\n*{track[1]}* • {track[2]} écoutes", inline=False)
    
    if top_artists:
        embed.add_field(name="🎤 Top Artiste", value=f"**{top_artists[0][0]}** • {top_artists[0][1]} écoutes", inline=True)
    
    if top_genres:
        embed.add_field(name="🎸 Top Genre", value=f"**{top_genres[0][0]}** • {top_genres[0][1]} écoutes", inline=True)
    
    embed.set_footer(text=f"🎉 Merci d'avoir écouté avec nous ! {emoji}")
    
    await interaction.edit_original_response(content=None, embed=embed)
    
    graph = bot.analytics.generate_listening_trend(days)
    if graph:
        file = discord.File(graph, filename="wrapped.png")
        await interaction.followup.send(file=file)

@bot.tree.command(name="recap", description="Affiche un récapitulatif complet Spotify")
async def recap_slash(interaction: discord.Interaction):
    """Récapitulatif Spotify complet"""
    await interaction.response.send_message("🔄 Génération du récapitulatif Spotify...")
    
    total_plays = bot.db.get_track_play_count()
    total_time_minutes = bot.db.get_total_listening_time()
    total_hours = total_time_minutes / 60
    total_days = total_hours / 24
    
    top_tracks = bot.db.get_top_tracks(10)
    top_artists = bot.db.get_top_artists(10)
    top_genres = bot.db.get_top_genres(5)
    
    color = bot.theme_manager.get_color('primary')
    
    embed = discord.Embed(
        title="🎵 Récapitulatif Spotify Complet",
        description="Toutes vos statistiques d'écoute",
        color=color,
        timestamp=datetime.now()
    )
    
    embed.add_field(
        name="⏱️ Temps d'écoute total",
        value=f"**{total_hours:.1f} heures** ({total_days:.2f} jours)\n📊 {total_plays} écoutes au total",
        inline=False
    )
    
    if top_tracks:
        tracks_text = "\n".join([f"**{i}.** {name} - *{artist}*\n└ {count} écoutes" for i, (name, artist, count, _, _) in enumerate(top_tracks[:5], 1)])
        embed.add_field(name="🎵 Top 5 Titres", value=tracks_text, inline=False)
    
    if top_artists:
        artists_text = "\n".join([f"**{i}.** {artist} - {count} écoutes" for i, (artist, count) in enumerate(top_artists[:5], 1)])
        embed.add_field(name="🎤 Top 5 Artistes", value=artists_text, inline=False)
    
    if top_genres:
        genres_text = "\n".join([f"**{i}.** {genre} - {count} écoutes" for i, (genre, count) in enumerate(top_genres, 1)])
        embed.add_field(name="🎸 Top 5 Genres", value=genres_text, inline=False)
    
    current = bot.get_current_track_full()
    if current and 'item' in current:
        track = current['item']
        embed.add_field(name="🎧 En cours d'écoute", value=f"**{track['artists'][0]['name']} - {track['name']}**", inline=False)
        if track['album']['images']:
            embed.set_thumbnail(url=track['album']['images'][0]['url'])
    
    embed.set_footer(text="Spotify Tracker", icon_url="https://i.imgur.com/vw8N4fy.png")
    
    await interaction.edit_original_response(content=None, embed=embed)

@bot.tree.command(name="listen", description="Affiche la musique en cours")
async def listen_slash(interaction: discord.Interaction):
    """Affiche la musique en cours"""
    current = bot.get_current_track_full()
    
    if not current or 'item' not in current:
        await interaction.response.send_message("❌ Aucune musique en cours")
        return
    
    track = current['item']
    artist_id = track['artists'][0]['id']
    genres = await bot.get_artist_genres(artist_id)
    
    await interaction.response.send_message("🎵 Musique actuelle:")
    await bot.send_music_notification(interaction.channel, track, genres)

@bot.tree.command(name="top", description="Affiche le top des écoutes")
@app_commands.describe(categorie="Catégorie (tracks/artists/genres)", limite="Nombre d'éléments (défaut: 10)")
async def top_slash(interaction: discord.Interaction, categorie: str = "tracks", limite: int = 10):
    """Affiche le top des écoutes"""
    color = bot.theme_manager.get_color('warning')
    
    if categorie.lower() in ['tracks', 'track', 'titres', 'titre']:
        results = bot.db.get_top_tracks(limite)
        embed = discord.Embed(title=f"🏆 Top {len(results)} Titres", color=color, timestamp=datetime.now())
        
        for i, (name, artist, count, _, image) in enumerate(results, 1):
            embed.add_field(name=f"{i}. {name}", value=f"🎤 {artist}\n🔢 {count} écoutes", inline=False)
        
        if results and results[0][4]:
            embed.set_thumbnail(url=results[0][4])
    
    elif categorie.lower() in ['artists', 'artist', 'artistes', 'artiste']:
        results = bot.db.get_top_artists(limite)
        embed = discord.Embed(title=f"🏆 Top {len(results)} Artistes", color=color, timestamp=datetime.now())
        
        for i, (artist, count) in enumerate(results, 1):
            embed.add_field(name=f"{i}. {artist}", value=f"🔢 {count} écoutes", inline=True)
    
    elif categorie.lower() in ['genres', 'genre']:
        results = bot.db.get_top_genres(limite)
        embed = discord.Embed(title=f"🏆 Top {len(results)} Genres", color=color, timestamp=datetime.now())
        
        for i, (genre, count) in enumerate(results, 1):
            embed.add_field(name=f"{i}. {genre}", value=f"🔢 {count} écoutes", inline=True)
    
    else:
        await interaction.response.send_message("❌ Catégorie invalide. Utilisez `tracks`, `artists` ou `genres`")
        return
    
    embed.set_footer(text="Spotify Tracker")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="help", description="Affiche toutes les commandes disponibles")
async def help_slash(interaction: discord.Interaction):
    """Affiche l'aide"""
    color = bot.theme_manager.get_color('primary')
    
    embed = discord.Embed(
        title="📚 Aide - Spotify Tracker Bot",
        description="Liste complète des commandes disponibles\n*Utilisez `/` pour les commandes slash*",
        color=color
    )
    
    # Configuration
    embed.add_field(
        name="⚙️ Configuration",
        value=(
            "`/setchannel` - Définir le canal des notifications\n"
            "`/theme` - Changer le thème du bot"
        ),
        inline=False
    )
    
    # Spotify - Consultation
    embed.add_field(
        name="🎵 Écoute & Consultation",
        value=(
            "`/listen` - Musique en cours\n"
            "`/top` - Top tracks/artists/genres\n"
            "`/search` - Rechercher une musique\n"
            "`/stats` - Statistiques rapides"
        ),
        inline=False
    )
    
    # Analyse & Rapports
    embed.add_field(
        name="📊 Analyses & Rapports",
        value=(
            "`/recap` - Récapitulatif complet\n"
            "`/wrapped` - Spotify Wrapped\n"
            "`/genres` - Top genres\n"
            "`/mood` - Analyse de mood\n"
            "`/trend` - Graphique d'évolution\n"
            "`/heatmap` - Carte de chaleur\n"
            "`/patterns` - Patterns d'écoute\n"
            "`/streak` - Streaks d'écoute"
        ),
        inline=False
    )
    
    # Suivi d'artistes
    embed.add_field(
        name="🔔 Suivi d'Artistes",
        value=(
            "`/follow` - Suivre un artiste\n"
            "`/unfollow` - Ne plus suivre un artiste\n"
            "`/following` - Liste des artistes suivis"
        ),
        inline=False
    )
    
    # Découvertes
    embed.add_field(
        name="🆕 Découvertes",
        value=(
            "`/new` - Nouvelles découvertes\n"
            "`/search` - Rechercher dans l'historique"
        ),
        inline=False
    )
    
    embed.add_field(
        name="💡 Astuce",
        value="La plupart des commandes acceptent des paramètres optionnels comme le nombre de jours ou la limite d'éléments.",
        inline=False
    )
    
    embed.set_footer(text="🤖 Spotify Tracker Bot v4.0 | Créé avec ❤️")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ========== LANCEMENT DU BOT ==========

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🤖 BOT DISCORD - SPOTIFY TRACKER v4.0")
    print("="*60 + "\n")
    
    if not all([DISCORD_TOKEN, SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REFRESH_TOKEN]):
        print("❌ Variables manquantes dans .env\n")
        exit(1)
    
    print("✅ Configuration valide")
    print("🚀 Démarrage du bot...\n")
    
    bot = SpotifyBot()
    
    try:
        bot.run(DISCORD_TOKEN)
    except KeyboardInterrupt:
        print("\n\n👋 Arrêt du bot...")
    except discord.LoginFailure:
        print("\n❌ Token Discord invalide")
    except Exception as e:
        print(f"\n❌ Erreur: {e}")