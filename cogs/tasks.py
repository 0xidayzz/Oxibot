import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
from utils.embeds import EmbedBuilder
import config

class Tasks(commands.Cog):
    def __init__(self, bot, db_manager, spotify_client):
        self.bot = bot
        self.db = db_manager
        self.spotify = spotify_client
        self.embed_builder = EmbedBuilder()
        self.current_track_id = None
        
        # Démarrer les tâches
        self.check_current_track.start()
        self.check_new_releases.start()
        self.send_weekly_wrapped.start()
        self.check_milestones.start()
        self.update_bot_status.start()
    
    def cog_unload(self):
        """Arrêter les tâches lors du déchargement"""
        self.check_current_track.cancel()
        self.check_new_releases.cancel()
        self.send_weekly_wrapped.cancel()
        self.check_milestones.cancel()
        self.update_bot_status.cancel()
    
    @tasks.loop(seconds=15)
    async def check_current_track(self):
        """Vérifie le titre en cours toutes les 15 secondes"""
        try:
            track = self.spotify.get_current_track()
            
            if track and track['track_id'] != self.current_track_id:
                self.current_track_id = track['track_id']
                
                # Sauvegarder dans la DB
                track_data = {
                    'track_id': track['track_id'],
                    'track_name': track['track_name'],
                    'artist_name': track['artist_name'],
                    'album_name': track['album_name'],
                    'duration_ms': track['duration_ms'],
                    'played_at': datetime.now(config.TIMEZONE),
                    'image_url': track['image_url']
                }
                self.db.save_track(track_data)
                
                # Envoyer dans le channel Spotify
                for guild in self.bot.guilds:
                    channel_config = self.db.get_channel_config(guild.id)
                    if channel_config and channel_config['spotify_channel_id']:
                        channel = self.bot.get_channel(channel_config['spotify_channel_id'])
                        if channel:
                            play_count = self.db.get_track_play_count(track['track_id'])
                            embed = self.embed_builder.now_playing(track, play_count)
                            await channel.send(embed=embed)
        
        except Exception as e:
            print(f"Erreur check_current_track: {e}")
    
    @check_current_track.before_loop
    async def before_check_current_track(self):
        await self.bot.wait_until_ready()
    
    @tasks.loop(hours=6)
    async def check_new_releases(self):
        """Vérifie les nouvelles sorties toutes les 6 heures"""
        try:
            # Récupérer les artistes suivis
            followed_artists = self.spotify.get_followed_artists()
            
            for artist_data in followed_artists:
                # Vérifier dans la DB
                conn = self.db.get_connection()
                cursor = conn.cursor(dictionary=True)
                cursor.execute("""
                    SELECT last_checked FROM followed_artists
                    WHERE artist_id = %s
                """, (artist_data['artist_id'],))
                result = cursor.fetchone()
                
                last_check = result['last_checked'] if result else datetime.now() - timedelta(days=30)
                
                # Récupérer les nouvelles sorties
                new_releases = self.spotify.get_artist_latest_releases(
                    artist_data['artist_id'],
                    last_check
                )
                
                # Envoyer les notifications
                for release in new_releases:
                    for guild in self.bot.guilds:
                        channel_config = self.db.get_channel_config(guild.id)
                        if channel_config and channel_config['news_channel_id']:
                            channel = self.bot.get_channel(channel_config['news_channel_id'])
                            if channel:
                                embed = self.embed_builder.new_release(release, artist_data['artist_name'])
                                await channel.send(embed=embed)
                    
                    # Sauvegarder dans la DB
                    cursor.execute("""
                        INSERT IGNORE INTO new_releases
                        (release_id, artist_id, release_name, release_type, release_date, image_url)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        release['release_id'],
                        release['artist_id'],
                        release['release_name'],
                        release['release_type'],
                        release['release_date'],
                        release['image_url']
                    ))
                
                # Mettre à jour last_checked
                cursor.execute("""
                    INSERT INTO followed_artists (artist_id, artist_name, last_checked)
                    VALUES (%s, %s, NOW())
                    ON DUPLICATE KEY UPDATE last_checked = NOW()
                """, (artist_data['artist_id'], artist_data['artist_name']))
                
                conn.commit()
                cursor.close()
                conn.close()
        
        except Exception as e:
            print(f"Erreur check_new_releases: {e}")
    
    @check_new_releases.before_loop
    async def before_check_new_releases(self):
        await self.bot.wait_until_ready()
    
    @tasks.loop(hours=168)  # Toutes les semaines
    async def send_weekly_wrapped(self):
        """Envoie un wrapped hebdomadaire"""
        try:
            # Vérifier si on est lundi
            if datetime.now().weekday() == 0:  # 0 = lundi
                stats = self.db.get_stats('week')
                top_tracks = self.db.get_top_tracks(5, 'week')
                top_artists = self.db.get_top_artists(5, 'week')
                
                for guild in self.bot.guilds:
                    channel_config = self.db.get_channel_config(guild.id)
                    if channel_config and channel_config['main_channel_id']:
                        channel = self.bot.get_channel(channel_config['main_channel_id'])
                        if channel:
                            embed = self.embed_builder.wrapped(stats, top_tracks, top_artists, "de la semaine")
                            await channel.send("📊 Ton wrapped hebdomadaire est arrivé !", embed=embed)
        
        except Exception as e:
            print(f"Erreur send_weekly_wrapped: {e}")
    
    @send_weekly_wrapped.before_loop
    async def before_send_weekly_wrapped(self):
        await self.bot.wait_until_ready()
    
    @tasks.loop(hours=1)
    async def check_milestones(self):
        """Vérifie les paliers atteints"""
        try:
            stats = self.db.get_stats('all')
            
            # Temps d'écoute
            total_hours = int(stats['total_time_ms'] / 1000 / 60 / 60) if stats['total_time_ms'] else 0
            for milestone in config.MILESTONES['listening_time']:
                if total_hours >= milestone:
                    if self.db.save_milestone('listening_time', milestone):
                        # Nouveau palier atteint !
                        for guild in self.bot.guilds:
                            channel_config = self.db.get_channel_config(guild.id)
                            if channel_config and channel_config['main_channel_id']:
                                channel = self.bot.get_channel(channel_config['main_channel_id'])
                                if channel:
                                    embed = self.embed_builder.milestone('listening_time', milestone, stats)
                                    await channel.send(embed=embed)
            
            # Nombre de titres
            total_tracks = stats['total_tracks'] or 0
            for milestone in config.MILESTONES['tracks_count']:
                if total_tracks >= milestone:
                    if self.db.save_milestone('tracks_count', milestone):
                        for guild in self.bot.guilds:
                            channel_config = self.db.get_channel_config(guild.id)
                            if channel_config and channel_config['main_channel_id']:
                                channel = self.bot.get_channel(channel_config['main_channel_id'])
                                if channel:
                                    embed = self.embed_builder.milestone('tracks_count', milestone, stats)
                                    await channel.send(embed=embed)
            
            # Nombre d'artistes
            unique_artists = stats['unique_artists'] or 0
            for milestone in config.MILESTONES['artists_count']:
                if unique_artists >= milestone:
                    if self.db.save_milestone('artists_count', milestone):
                        for guild in self.bot.guilds:
                            channel_config = self.db.get_channel_config(guild.id)
                            if channel_config and channel_config['main_channel_id']:
                                channel = self.bot.get_channel(channel_config['main_channel_id'])
                                if channel:
                                    embed = self.embed_builder.milestone('artists_count', milestone, stats)
                                    await channel.send(embed=embed)
        
        except Exception as e:
            print(f"Erreur check_milestones: {e}")
    
    @check_milestones.before_loop
    async def before_check_milestones(self):
        await self.bot.wait_until_ready()
    
    @tasks.loop(minutes=5)
    async def update_bot_status(self):
        """Met à jour le statut du bot"""
        try:
            stats = self.db.get_stats('all')
            top_tracks = self.db.get_top_tracks(1, 'all')
            top_artists = self.db.get_top_artists(1, 'all')
            
            total_hours = int(stats['total_time_ms'] / 1000 / 60 / 60) if stats['total_time_ms'] else 0
            
            status_messages = [
                f"🎧 {total_hours}h d'écoute",
                f"🎵 {top_tracks[0]['track_name']}" if top_tracks else "🎵 Aucune écoute",
                f"🎤 {top_artists[0]['artist_name']}" if top_artists else "🎤 Aucun artiste"
            ]
            
            # Alterner entre les messages
            import random
            message = random.choice(status_messages)
            
            await self.bot.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.listening,
                    name=message
                )
            )
        
        except Exception as e:
            print(f"Erreur update_bot_status: {e}")
    
    @update_bot_status.before_loop
    async def before_update_bot_status(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    db_manager = bot.db_manager
    spotify_client = bot.spotify_client
    await bot.add_cog(Tasks(bot, db_manager, spotify_client))