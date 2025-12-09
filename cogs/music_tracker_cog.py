# cogs/music_tracker_cog.py
import discord
from discord.ext import commands, tasks
from datetime import datetime
import time

# Import des helpers
from helpers.spotify_auth import spotify_client
from helpers.database import get_db_connection, log_track, PARIS_TZ

class MusicTracker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.last_track_id = None
        self.track_changes_loop.start()

    def cog_unload(self):
        self.track_changes_loop.cancel()

    @tasks.loop(seconds=10) # Vérification toutes les 10 secondes
    async def track_changes_loop(self):
        await self.bot.wait_until_ready()
        
        # 1. Récupérer l'information Spotify
        current_track = spotify_client.get_currently_playing()

        if current_track and current_track.get('is_playing') and current_track.get('item'):
            track_data = current_track['item']
            
            track_info = {
                'id': track_data['id'],
                'name': track_data['name'],
                'artist': track_data['artists'][0]['name'],
                'album': track_data['album']['name'],
                'image_url': track_data['album']['images'][0]['url'],
                'duration_ms': track_data['duration_ms'],
                'progress_ms': current_track['progress_ms'],
                'url': track_data['external_urls']['spotify']
            }
            
            # 2. Vérifier si la musique a changé
            if track_info['id'] != self.last_track_id:
                self.last_track_id = track_info['id']
                
                # 3. Loguer dans la DB
                log_track(track_info)

                # 4. Envoyer le message Discord
                await self.send_music_update(track_info)

    def _get_channel_id(self, guild_id):
        """Récupère l'ID du salon 'musique' pour la guilde."""
        conn = get_db_connection()
        settings = conn.execute(
            'SELECT music_channel_id, theme FROM server_settings WHERE guild_id = ?', 
            (guild_id,)
        ).fetchone()
        conn.close()
        return settings['music_channel_id'] if settings else None

    async def send_music_update(self, track_info):
        """Crée et envoie l'Embed de la musique actuelle."""
        
        # Conversion du temps (ms -> min:sec)
        total_time = divmod(track_info['duration_ms'] // 1000, 60)
        
        # Heure de Paris
        now_paris = datetime.now(PARIS_TZ).strftime('%H:%M:%S')

        # Thème par défaut: Violet Simple
        embed = discord.Embed(
            title=f"🎶 Nouvelle Musique Lancée : {track_info['name']}",
            description=f"**Artiste :** {track_info['artist']}\n**Album :** *{track_info['album']}*",
            color=0x9B59B6 # Violet
        )
        embed.set_thumbnail(url=track_info['image_url'])
        
        embed.add_field(name="Durée du titre", 
                        value=f"⏱️ `{total_time[0]:02}:{total_time[1]:02}`", 
                        inline=True)
        embed.add_field(name="Lancement à", 
                        value=f"⌚ {now_paris} (CET)", 
                        inline=True)
        embed.add_field(name="Lien", 
                        value=f"🔗 [Écouter sur Spotify]({track_info['url']})", 
                        inline=False)
        
        embed.set_footer(text="Suivi en temps réel | Tracker")

        # --- Envoi à tous les serveurs ---
        for guild in self.bot.guilds:
            channel_id = self._get_channel_id(guild.id)
            if channel_id:
                channel = self.bot.get_channel(channel_id)
                if channel:
                    try:
                        await channel.send(embed=embed)
                    except discord.Forbidden:
                        print(f"Pas les permissions d'envoyer dans le salon {channel.name} de {guild.name}")

    @commands.command(name='song')
    async def song_command(self, ctx):
        """Affiche le titre actuellement écouté."""
        current_track = spotify_client.get_currently_playing()
        if not current_track or not current_track.get('is_playing'):
            return await ctx.send("Je ne vous vois écouter aucune musique actuellement.")
        
        track_data = current_track['item']
        track_info = {
            'id': track_data['id'],
            'name': track_data['name'],
            'artist': track_data['artists'][0]['name'],
            'album': track_data['album']['name'],
            'image_url': track_data['album']['images'][0]['url'],
            'duration_ms': track_data['duration_ms'],
            'progress_ms': current_track['progress_ms'],
            'url': track_data['external_urls']['spotify']
        }
        
        # Envoie l'embed dans le canal de commande
        await self.send_music_update(track_info)

def setup(bot):
    bot.add_cog(MusicTracker(bot))