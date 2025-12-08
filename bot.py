import discord
from discord.ext import commands, tasks
import requests
from datetime import datetime
import os
from dotenv import load_dotenv
import base64

# Charge les variables d'environnement depuis le fichier .env
load_dotenv()

# Configuration
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
GITHUB_USERNAME = os.getenv('GITHUB_USERNAME')
SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
SPOTIFY_REFRESH_TOKEN = os.getenv('SPOTIFY_REFRESH_TOKEN')
STATS_CHANNEL_ID = int(os.getenv('STATS_CHANNEL_ID', '0'))
MUSIC_CHANNEL_ID = int(os.getenv('MUSIC_CHANNEL_ID', '0'))  # Canal pour les notifs musique

class ProfileUpdater(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.presences = True
        intents.guilds = True
        super().__init__(command_prefix='!', intents=intents)
        
        self.spotify_access_token = None
        self.last_push = "Chargement..."
        self.last_track_id = None  # Pour détecter les changements de musique
        self.current_track_data = None  # Données complètes de la track actuelle
        self.stats_message = None
        
    async def on_ready(self):
        print("\n" + "="*60)
        print(f"✅ Bot connecté en tant que: {self.user}")
        print(f"📊 ID: {self.user.id}")
        print("="*60)
        print("\n🔄 Démarrage de la mise à jour automatique...")
        print("⏰ Intervalle: toutes les 30 secondes pour la musique")
        print("⏹️  Pour arrêter: Ctrl+C\n")
        
        # Première mise à jour immédiate
        await self.update_data()
        
        # Démarre les boucles
        if not self.update_loop.is_running():
            self.update_loop.start()
        if not self.music_check_loop.is_running():
            self.music_check_loop.start()
    
    def get_github_last_push(self):
        """Récupère la date du dernier push Git sur GitHub"""
        try:
            headers = {
                "Authorization": f"token {GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3+json"
            }
            url = f"https://api.github.com/users/{GITHUB_USERNAME}/events"
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                events = response.json()
                
                for event in events:
                    if event['type'] == 'PushEvent':
                        date_str = event['created_at']
                        date = datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%SZ')
                        formatted_date = date.strftime('%d/%m/%Y à %H:%M')
                        repo_name = event['repo']['name']
                        return f"{formatted_date} ({repo_name})"
                
                return "Aucun push récent trouvé"
            
            elif response.status_code == 401:
                return "❌ Token GitHub invalide"
            else:
                return f"❌ Erreur API GitHub ({response.status_code})"
                
        except Exception as e:
            print(f"⚠️ Erreur GitHub: {e}")
            return "❌ Erreur GitHub"
    
    def refresh_spotify_token(self):
        """Rafraîchit le token d'accès Spotify"""
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
                token_data = response.json()
                self.spotify_access_token = token_data['access_token']
                return True
            else:
                print(f"⚠️ Erreur refresh Spotify: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"⚠️ Exception refresh Spotify: {e}")
            return False
    
    def get_spotify_headers(self):
        """Obtient les headers avec token valide"""
        if not self.spotify_access_token:
            self.refresh_spotify_token()
        return {"Authorization": f"Bearer {self.spotify_access_token}"}
    
    def get_current_track_full(self):
        """Récupère les données complètes de la track en cours de lecture"""
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
        """Vérifie si la musique a changé et envoie une notification"""
        try:
            current_data = self.get_current_track_full()
            
            if not current_data or 'item' not in current_data:
                return
            
            track = current_data['item']
            track_id = track['id']
            
            # Si c'est une nouvelle musique
            if track_id != self.last_track_id and MUSIC_CHANNEL_ID > 0:
                self.last_track_id = track_id
                self.current_track_data = track
                
                # Envoie la notification
                channel = self.get_channel(MUSIC_CHANNEL_ID)
                if channel:
                    await self.send_music_notification(channel, track)
                    print(f"🎵 Nouvelle musique détectée: {track['artists'][0]['name']} - {track['name']}")
            
        except Exception as e:
            print(f"⚠️ Erreur check music: {e}")
    
    async def send_music_notification(self, channel, track):
        """Envoie une notification de changement de musique avec image"""
        try:
            artist = track['artists'][0]['name']
            title = track['name']
            album = track['album']['name']
            image_url = track['album']['images'][0]['url'] if track['album']['images'] else None
            spotify_url = track['external_urls']['spotify']
            duration_ms = track['duration_ms']
            duration_min = duration_ms // 60000
            duration_sec = (duration_ms % 60000) // 1000
            
            embed = discord.Embed(
                title="🎵 Nouvelle musique en cours",
                description=f"**[{title}]({spotify_url})**",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            
            embed.add_field(name="🎤 Artiste", value=artist, inline=True)
            embed.add_field(name="💿 Album", value=album, inline=True)
            embed.add_field(name="⏱️ Durée", value=f"{duration_min}:{duration_sec:02d}", inline=True)
            
            if image_url:
                embed.set_thumbnail(url=image_url)
            
            embed.set_footer(text="Spotify", icon_url="https://i.imgur.com/vw8N4fy.png")
            
            await channel.send(embed=embed)
            
        except Exception as e:
            print(f"⚠️ Erreur notification musique: {e}")
    
    def get_spotify_top_stats(self, time_range='short_term'):
        """Récupère les statistiques Spotify (top artistes et tracks)
        time_range: 'short_term' (4 semaines), 'medium_term' (6 mois), 'long_term' (plusieurs années)
        """
        try:
            headers = self.get_spotify_headers()
            
            # Top Artistes
            top_artists_url = f"https://api.spotify.com/v1/me/top/artists?limit=5&time_range={time_range}"
            artists_response = requests.get(top_artists_url, headers=headers, timeout=10)
            
            # Top Tracks
            top_tracks_url = f"https://api.spotify.com/v1/me/top/tracks?limit=5&time_range={time_range}"
            tracks_response = requests.get(top_tracks_url, headers=headers, timeout=10)
            
            result = {
                'top_artists': [],
                'top_tracks': [],
                'error': None
            }
            
            if artists_response.status_code == 401 or tracks_response.status_code == 401:
                self.refresh_spotify_token()
                headers = self.get_spotify_headers()
                artists_response = requests.get(top_artists_url, headers=headers, timeout=10)
                tracks_response = requests.get(top_tracks_url, headers=headers, timeout=10)
            
            if artists_response.status_code == 200:
                data = artists_response.json()
                result['top_artists'] = data.get('items', [])
            
            if tracks_response.status_code == 200:
                data = tracks_response.json()
                result['top_tracks'] = data.get('items', [])
            
            return result
            
        except Exception as e:
            print(f"⚠️ Erreur stats Spotify: {e}")
            return {'top_artists': [], 'top_tracks': [], 'error': str(e)}
    
    def get_recently_played(self):
        """Récupère les dernières écoutes pour calculer le temps d'écoute"""
        try:
            headers = self.get_spotify_headers()
            url = "https://api.spotify.com/v1/me/player/recently-played?limit=50"
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 401:
                self.refresh_spotify_token()
                headers = self.get_spotify_headers()
                response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('items', [])
            
            return []
            
        except Exception as e:
            print(f"⚠️ Erreur recently played: {e}")
            return []
    
    async def update_data(self):
        """Met à jour toutes les données GitHub"""
        print(f"\n🔄 Mise à jour GitHub... ({datetime.now().strftime('%H:%M:%S')})")
        
        self.last_push = self.get_github_last_push()
        print(f"   📂 GitHub: {self.last_push}")
        
        # Met à jour le message épinglé si configuré
        if STATS_CHANNEL_ID > 0:
            await self.update_stats_message()
        
        print("✅ Mise à jour terminée")
    
    async def update_stats_message(self):
        """Met à jour le message épinglé avec les stats GitHub"""
        try:
            channel = self.get_channel(STATS_CHANNEL_ID)
            if not channel:
                return
            
            embed = discord.Embed(
                title="📊 Statistiques GitHub",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            embed.add_field(
                name="🔧 Dernier Push Git",
                value=self.last_push,
                inline=False
            )
            
            embed.set_footer(text="🔄 Mise à jour automatique")
            
            if self.stats_message:
                try:
                    await self.stats_message.edit(embed=embed)
                    return
                except discord.NotFound:
                    self.stats_message = None
            
            self.stats_message = await channel.send(embed=embed)
            try:
                await self.stats_message.pin()
            except:
                pass
                
        except Exception as e:
            print(f"⚠️ Erreur mise à jour message: {e}")
    
    @tasks.loop(minutes=5)
    async def update_loop(self):
        """Boucle de mise à jour GitHub toutes les 5 minutes"""
        await self.update_data()
    
    @tasks.loop(seconds=30)
    async def music_check_loop(self):
        """Vérifie les changements de musique toutes les 30 secondes"""
        await self.check_music_change()
    
    @update_loop.before_loop
    async def before_update_loop(self):
        await self.wait_until_ready()
    
    @music_check_loop.before_loop
    async def before_music_check_loop(self):
        await self.wait_until_ready()

# Commandes
@commands.command(name='stats')
async def stats(ctx, periode: str = 'court'):
    """Affiche les statistiques Spotify détaillées
    Périodes: court (4 semaines), moyen (6 mois), long (toutes les données)
    """
    bot = ctx.bot
    
    # Détermine la période
    time_ranges = {
        'court': 'short_term',
        'moyen': 'medium_term',
        'long': 'long_term'
    }
    
    time_range = time_ranges.get(periode.lower(), 'short_term')
    
    periode_text = {
        'short_term': '4 dernières semaines',
        'medium_term': '6 derniers mois',
        'long_term': 'Toutes les données'
    }
    
    await ctx.send("🔄 Récupération de vos statistiques Spotify...")
    
    # Récupère les stats
    stats_data = bot.get_spotify_top_stats(time_range)
    recently_played = bot.get_recently_played()
    
    # Calcul du temps d'écoute (basé sur les 50 dernières écoutes)
    total_listening_time = sum(item['track']['duration_ms'] for item in recently_played) // 60000
    
    # Création de l'embed
    embed = discord.Embed(
        title="🎵 Vos Statistiques Spotify",
        description=f"📅 Période: **{periode_text[time_range]}**",
        color=discord.Color.green(),
        timestamp=datetime.now()
    )
    
    # Top Artistes
    if stats_data['top_artists']:
        artists_text = ""
        for i, artist in enumerate(stats_data['top_artists'], 1):
            genres = ", ".join(artist['genres'][:2]) if artist['genres'] else "Aucun genre"
            artists_text += f"**{i}.** {artist['name']}\n└ *{genres}*\n"
        
        embed.add_field(
            name="🎤 Top Artistes",
            value=artists_text or "Aucune donnée",
            inline=False
        )
    
    # Top Titres
    if stats_data['top_tracks']:
        tracks_text = ""
        for i, track in enumerate(stats_data['top_tracks'], 1):
            artist_name = track['artists'][0]['name']
            track_name = track['name']
            tracks_text += f"**{i}.** {track_name}\n└ *par {artist_name}*\n"
        
        embed.add_field(
            name="🎵 Top Titres",
            value=tracks_text or "Aucune donnée",
            inline=False
        )
    
    # Temps d'écoute
    embed.add_field(
        name="⏱️ Temps d'écoute",
        value=f"**~{total_listening_time} minutes** (50 dernières écoutes)",
        inline=False
    )
    
    # Musique actuelle
    current_track = bot.get_current_track_full()
    if current_track and 'item' in current_track:
        track = current_track['item']
        current_text = f"🎵 **{track['artists'][0]['name']} - {track['name']}**"
        embed.add_field(
            name="🎧 En cours d'écoute",
            value=current_text,
            inline=False
        )
        
        # Image de l'album
        if track['album']['images']:
            embed.set_thumbnail(url=track['album']['images'][0]['url'])
    
    embed.set_footer(text="Spotify Stats • Utilisez !stats court/moyen/long", 
                     icon_url="https://i.imgur.com/vw8N4fy.png")
    
    await ctx.send(embed=embed)

@commands.command(name='update')
async def update(ctx):
    """Force une mise à jour des données GitHub"""
    await ctx.send("🔄 Mise à jour forcée en cours...")
    await ctx.bot.update_data()
    await ctx.send("✅ Mise à jour terminée !")

@commands.command(name='setstats')
@commands.has_permissions(administrator=True)
async def setstats(ctx):
    """Définit le canal actuel comme canal de stats GitHub"""
    global STATS_CHANNEL_ID
    STATS_CHANNEL_ID = ctx.channel.id
    
    await ctx.send(f"✅ Canal de stats GitHub défini : {ctx.channel.mention}\n"
                   f"💡 Ajoutez `STATS_CHANNEL_ID={ctx.channel.id}` dans votre .env")
    
    await ctx.bot.update_stats_message()

@commands.command(name='setmusic')
@commands.has_permissions(administrator=True)
async def setmusic(ctx):
    """Définit le canal actuel comme canal de notifications musique"""
    global MUSIC_CHANNEL_ID
    MUSIC_CHANNEL_ID = ctx.channel.id
    
    await ctx.send(f"🎵 Canal de notifications musique défini : {ctx.channel.mention}\n"
                   f"💡 Ajoutez `MUSIC_CHANNEL_ID={ctx.channel.id}` dans votre .env\n"
                   f"✨ Je vais maintenant poster ici à chaque changement de musique !")

@commands.command(name='playing')
async def playing(ctx):
    """Affiche la musique actuellement en cours de lecture"""
    bot = ctx.bot
    current_track = bot.get_current_track_full()
    
    if not current_track or 'item' not in current_track:
        await ctx.send("❌ Aucune musique en cours de lecture")
        return
    
    track = current_track['item']
    await bot.send_music_notification(ctx.channel, track)

# Vérifie la configuration
def check_config():
    """Vérifie que toutes les variables d'environnement sont définies"""
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
        print("\n❌ ERREUR: Variables manquantes dans .env:")
        for var in missing:
            print(f"   - {var}")
        print("\nVeuillez remplir le fichier .env avec vos tokens.\n")
        return False
    
    if STATS_CHANNEL_ID == 0:
        print("\n⚠️ STATS_CHANNEL_ID non défini - utilisez !setstats")
    
    if MUSIC_CHANNEL_ID == 0:
        print("⚠️ MUSIC_CHANNEL_ID non défini - utilisez !setmusic")
    
    print()
    return True

# Point d'entrée du programme
if __name__ == "__main__":
    print("\n" + "="*60)
    print("🤖 BOT DISCORD - SPOTIFY & GITHUB TRACKER")
    print("="*60 + "\n")
    
    if not check_config():
        exit(1)
    
    print("✅ Configuration valide")
    print("🚀 Démarrage du bot...\n")
    
    # Crée le bot
    bot = ProfileUpdater()
    
    # Ajoute les commandes
    bot.add_command(stats)
    bot.add_command(update)
    bot.add_command(setstats)
    bot.add_command(setmusic)
    bot.add_command(playing)
    
    try:
        bot.run(DISCORD_TOKEN)
    except KeyboardInterrupt:
        print("\n\n👋 Arrêt du bot...")
        print("✅ Bot arrêté proprement\n")
    except discord.LoginFailure:
        print("\n❌ ERREUR: Token Discord invalide")
        print("Vérifiez votre DISCORD_TOKEN dans le fichier .env\n")
    except Exception as e:
        print(f"\n❌ Erreur fatale: {e}\n")