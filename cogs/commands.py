import discord
from discord.ext import commands
from discord import app_commands
from utils.embeds import EmbedBuilder
from utils.graphs import GraphGenerator
import config

class Commands(commands.Cog):
    def __init__(self, bot, db_manager, spotify_client):
        self.bot = bot
        self.db = db_manager
        self.spotify = spotify_client
        self.embed_builder = EmbedBuilder()
        self.graph_gen = GraphGenerator(db_manager)
    
    @app_commands.command(name="setchannel", description="Configure un channel pour les notifications")
    @app_commands.describe(
        channel_type="Type de channel (Spotify/News/Main)",
        channel="Le channel à configurer"
    )
    @app_commands.choices(channel_type=[
        app_commands.Choice(name="Spotify", value="spotify"),
        app_commands.Choice(name="News", value="news"),
        app_commands.Choice(name="Main", value="main")
    ])
    async def setchannel(self, interaction: discord.Interaction, channel_type: str, channel: discord.TextChannel):
        """Configure un channel"""
        self.db.set_channel(interaction.guild_id, channel_type, channel.id)
        
        channel_names = {
            'spotify': 'Spotify (titres en cours)',
            'news': 'News (nouvelles sorties)',
            'main': 'Main (wrapped & paliers)'
        }
        
        embed = discord.Embed(
            title="✅ Channel configuré",
            description=f"Le channel {channel.mention} a été configuré pour **{channel_names[channel_type]}**",
            color=config.DEFAULT_THEME['color']
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="wrapped", description="Affiche ton wrapped")
    @app_commands.describe(period="Période du wrapped")
    @app_commands.choices(period=[
        app_commands.Choice(name="Semaine", value="week"),
        app_commands.Choice(name="Mois", value="month"),
        app_commands.Choice(name="Année", value="year"),
        app_commands.Choice(name="Tout", value="all")
    ])
    async def wrapped(self, interaction: discord.Interaction, period: str = "all"):
        """Envoie un wrapped"""
        await interaction.response.defer()
        
        stats = self.db.get_stats(period)
        top_tracks = self.db.get_top_tracks(10, period)
        top_artists = self.db.get_top_artists(10, period)
        
        period_names = {
            'week': 'de la semaine',
            'month': 'du mois',
            'year': 'de l\'année',
            'all': 'total'
        }
        
        embed = self.embed_builder.wrapped(stats, top_tracks, top_artists, period_names[period])
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="graph", description="Génère un graphique")
    @app_commands.describe(
        graph_type="Type de graphique",
        period="Période"
    )
    @app_commands.choices(
        graph_type=[
            app_commands.Choice(name="Artistes", value="artiste"),
            app_commands.Choice(name="Titres écoutés", value="titre"),
            app_commands.Choice(name="Nouveaux titres", value="newTitre"),
            app_commands.Choice(name="Temps d'écoute", value="time")
        ],
        period=[
            app_commands.Choice(name="Semaine", value="week"),
            app_commands.Choice(name="Mois", value="month"),
            app_commands.Choice(name="Année", value="year")
        ]
    )
    async def graph(self, interaction: discord.Interaction, graph_type: str, period: str):
        """Génère un graphique"""
        await interaction.response.defer()
        
        buffer = self.graph_gen.generate_graph(graph_type, period)
        file = discord.File(buffer, filename='graph.png')
        
        embed = discord.Embed(
            title=f"📊 Graphique - {graph_type.title()}",
            color=config.DEFAULT_THEME['color']
        )
        embed.set_image(url="attachment://graph.png")
        
        await interaction.followup.send(embed=embed, file=file)
    
    @app_commands.command(name="info", description="Affiche les infos d'un titre ou artiste")
    @app_commands.describe(
        query="Nom du titre ou de l'artiste",
        search_type="Type de recherche"
    )
    @app_commands.choices(search_type=[
        app_commands.Choice(name="Titre", value="track"),
        app_commands.Choice(name="Artiste", value="artist")
    ])
    async def info(self, interaction: discord.Interaction, query: str, search_type: str):
        """Affiche les infos"""
        await interaction.response.defer()
        
        if search_type == "track":
            track_info = self.spotify.get_track_info(track_name=query)
            if not track_info:
                await interaction.followup.send("❌ Titre introuvable !")
                return
            
            # Récupérer les stats de la DB
            conn = self.db.get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT 
                    COUNT(*) as play_count,
                    MIN(played_at) as first_listen
                FROM listening_history
                WHERE track_id = %s
            """, (track_info['track_id'],))
            db_stats = cursor.fetchone()
            cursor.close()
            conn.close()
            
            embed = self.embed_builder.track_info(track_info, db_stats if db_stats['play_count'] > 0 else None)
            await interaction.followup.send(embed=embed)
        
        else:  # artist
            artist_info = self.spotify.get_artist_info(artist_name=query)
            if not artist_info:
                await interaction.followup.send("❌ Artiste introuvable !")
                return
            
            # Récupérer les stats de la DB
            conn = self.db.get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT 
                    COUNT(*) as play_count,
                    SUM(duration_ms) as total_time_ms
                FROM listening_history
                WHERE artist_name LIKE %s
            """, (f"%{artist_info['artist_name']}%",))
            db_stats = cursor.fetchone()
            cursor.close()
            conn.close()
            
            embed = self.embed_builder.artist_info(artist_info, db_stats if db_stats['play_count'] > 0 else None)
            await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="song", description="Affiche le titre en cours de lecture")
    async def song(self, interaction: discord.Interaction):
        """Affiche le titre actuel"""
        await interaction.response.defer()
        
        track = self.spotify.get_current_track()
        if not track:
            await interaction.followup.send("❌ Aucun titre en cours de lecture !")
            return
        
        play_count = self.db.get_track_play_count(track['track_id'])
        embed = self.embed_builder.now_playing(track, play_count)
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="top", description="Affiche ton top titres ou artistes")
    @app_commands.describe(
        top_type="Type de top",
        period="Période"
    )
    @app_commands.choices(
        top_type=[
            app_commands.Choice(name="Titres", value="titre"),
            app_commands.Choice(name="Artistes", value="artiste")
        ],
        period=[
            app_commands.Choice(name="Semaine", value="week"),
            app_commands.Choice(name="Mois", value="month"),
            app_commands.Choice(name="Année", value="year"),
            app_commands.Choice(name="Tout", value="all")
        ]
    )
    async def top(self, interaction: discord.Interaction, top_type: str, period: str = "all"):
        """Affiche le top"""
        await interaction.response.defer()
        
        period_names = {
            'week': 'de la semaine',
            'month': 'du mois',
            'year': 'de l\'année',
            'all': 'de tous les temps'
        }
        
        if top_type == "titre":
            tracks = self.db.get_top_tracks(10, period)
            
            embed = discord.Embed(
                title=f"🏆 Top Titres {period_names[period]}",
                color=config.DEFAULT_THEME['color']
            )
            
            description = ""
            for i, track in enumerate(tracks, 1):
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                description += f"{medal} **{track['track_name']}** - {track['artist_name']}\n    └ {track['play_count']} écoutes\n\n"
            
            embed.description = description
            
            if tracks and tracks[0].get('image_url'):
                embed.set_thumbnail(url=tracks[0]['image_url'])
        
        else:  # artiste
            artists = self.db.get_top_artists(10, period)
            
            embed = discord.Embed(
                title=f"🎤 Top Artistes {period_names[period]}",
                color=config.DEFAULT_THEME['color']
            )
            
            description = ""
            for i, artist in enumerate(artists, 1):
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                hours = artist['total_time_ms'] / 1000 / 60 / 60
                description += f"{medal} **{artist['artist_name']}**\n    └ {artist['play_count']} écoutes • {hours:.1f}h\n\n"
            
            embed.description = description
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="theme", description="Modifie le thème du bot")
    @app_commands.describe(color="Couleur en hexadécimal (ex: #9B59B6)")
    async def theme(self, interaction: discord.Interaction, color: str = None):
        """Modifie le thème"""
        if color:
            try:
                # Convertir hex en int
                color_int = int(color.replace('#', ''), 16)
                
                # Sauvegarder dans la DB
                conn = self.db.get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO config (guild_id, theme_color)
                    VALUES (%s, %s)
                    ON DUPLICATE KEY UPDATE theme_color = %s
                """, (interaction.guild_id, color_int, color_int))
                conn.commit()
                cursor.close()
                conn.close()
                
                embed = discord.Embed(
                    title="✅ Thème modifié",
                    description=f"La couleur a été changée en {color}",
                    color=color_int
                )
            except:
                embed = discord.Embed(
                    title="❌ Erreur",
                    description="Format de couleur invalide ! Utilise un format hexadécimal (ex: #9B59B6)",
                    color=0xFF0000
                )
        else:
            embed = discord.Embed(
                title="🎨 Thème actuel",
                description="Utilise `/theme #COULEUR` pour changer la couleur",
                color=config.DEFAULT_THEME['color']
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    db_manager = bot.db_manager
    spotify_client = bot.spotify_client
    await bot.add_cog(Commands(bot, db_manager, spotify_client))