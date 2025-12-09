# cogs/music_tracker_cog.py
import discord
from discord.ext import commands, tasks
import os
from datetime import datetime
import pytz

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

        if current_track and current_track.get('is_playing'):
            track_info = {
                'id': current_track['item']['id'],
                'name': current_track['item']['name'],
                'artist': current_track['item']['artists'][0]['name'],
                'album': current_track['item']['album']['name'],
                'image_url': current_track['item']['album']['images'][0]['url'],
                'duration_ms': current_track['item']['duration_ms'],
                'progress_ms': current_track['progress_ms'],
                'url': current_track['item']['external_urls']['spotify']
            }
            
            # 2. Vérifier si la musique a changé
            if track_info['id'] != self.last_track_id:
                self.last_track_id = track_info['id']
                
                # 3. Loguer dans la DB (pour les statistiques)
                # NOTE: Pour la première fois, on suppose que l'écoute commence maintenant
                # Pour un tracking parfait, on doit loguer quand la chanson se termine.
                # Simplification: on log quand la chanson change.
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
        
        # --- Créez le style d'Embed "Violet Simple" (le thème par défaut) ---
        
        # Conversion du temps (ms -> min:sec)
        total_time = divmod(track_info['duration_ms'] // 1000, 60)
        progress_time = divmod(track_info['progress_ms'] // 1000, 60)
        
        # Heure de Paris pour le lancement
        now_paris = datetime.now(PARIS_TZ).strftime('%H:%M:%S')

        embed = discord.Embed(
            title=f"🎶 {track_info['name']}",
            description=f"**{track_info['artist']}** - *{track_info['album']}*",
            color=0x9B59B6 # Violet
        )
        embed.set_thumbnail(url=track_info['image_url'])
        
        # Affichage du temps
        embed.add_field(name="Durée", 
                        value=f"`{total_time[0]:02}:{total_time[1]:02}`", 
                        inline=True)
        embed.add_field(name="Lancement", 
                        value=f"⌚ {now_paris} (Heure de Paris)", 
                        inline=True)
        embed.add_field(name="Lien", 
                        value=f"[Écouter sur Spotify]({track_info['url']})", 
                        inline=False)
        
        embed.set_footer(text="Suivi en temps réel | Bot propulsé par Spotify")

        # --- Envoi à tous les serveurs ---
        for guild in self.bot.guilds:
            channel_id = self._get_channel_id(guild.id)
            if channel_id:
                channel = self.bot.get_channel(channel_id)
                if channel:
                    try:
                        # Effacer le message précédent (optionnel pour garder le salon propre)
                        # Ceci nécessite l'historique de messages. Simplification: on envoie un nouveau message.
                        await channel.send(embed=embed)
                    except discord.Forbidden:
                        print(f"Pas les permissions d'envoyer dans le salon {channel.name}")

    @track_changes_loop.before_loop
    async def before_track_changes(self):
        print("Attente du démarrage du bot et du client Spotify...")
        await self.bot.wait_until_ready()
        
    # --- Commandes ---

    @commands.command(name='song')
    async def song_command(self, ctx):
        """Affiche le titre actuellement écouté (sans attendre le loop)."""
        current_track = spotify_client.get_currently_playing()
        if not current_track or not current_track.get('is_playing'):
            return await ctx.send("Je ne vous vois écouter aucune musique actuellement.")
        
        # Réutilise la logique pour générer l'embed
        track_info = {
            'id': current_track['item']['id'],
            'name': current_track['item']['name'],
            'artist': current_track['item']['artists'][0]['name'],
            'album': current_track['item']['album']['name'],
            'image_url': current_track['item']['album']['images'][0]['url'],
            'duration_ms': current_track['item']['duration_ms'],
            'progress_ms': current_track['progress_ms'],
            'url': current_track['item']['external_urls']['spotify']
        }
        await self.send_music_update(track_info)

def setup(bot):
    bot.add_cog(MusicTracker(bot))