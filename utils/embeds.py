import discord
from datetime import datetime
import config

class EmbedBuilder:
    def __init__(self, theme=None):
        self.theme = theme or config.DEFAULT_THEME
    
    def _format_duration(self, ms):
        """Convertit des millisecondes en format lisible"""
        seconds = ms // 1000
        minutes = seconds // 60
        hours = minutes // 60
        
        if hours > 0:
            return f"{hours}h {minutes % 60}m"
        return f"{minutes}m {seconds % 60}s"
    
    def now_playing(self, track_data, play_count):
        """Embed pour le titre en cours de lecture"""
        embed = discord.Embed(
            title=f"{self.theme['emojis']['music']} En écoute",
            description=f"**[{track_data['track_name']}]({track_data['spotify_url']})**",
            color=self.theme['color'],
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name=f"{self.theme['emojis']['artist']} Artiste",
            value=track_data['artist_name'],
            inline=True
        )
        
        embed.add_field(
            name=f"{self.theme['emojis']['album']} Album",
            value=track_data['album_name'],
            inline=True
        )
        
        embed.add_field(
            name=f"{self.theme['emojis']['headphones']} Écoutes",
            value=f"{play_count} fois",
            inline=True
        )
        
        if track_data['image_url']:
            embed.set_thumbnail(url=track_data['image_url'])
        
        embed.set_footer(text="Spotify Tracker")
        
        return embed
    
    def wrapped(self, stats, top_tracks, top_artists, period_name):
        """Embed pour le wrapped"""
        total_hours = (stats['total_time_ms'] / 1000 / 60 / 60) if stats['total_time_ms'] else 0
        
        embed = discord.Embed(
            title=f"{self.theme['emojis']['trophy']} Ton Wrapped {period_name}",
            description=f"Voici un récapitulatif de ton activité musicale {self.theme['emojis']['headphones']}",
            color=self.theme['color'],
            timestamp=datetime.now()
        )
        
        # Stats générales
        stats_text = f"""
{self.theme['emojis']['music']} **{stats['total_tracks']}** titres écoutés
{self.theme['emojis']['chart']} **{stats['unique_tracks']}** titres uniques
{self.theme['emojis']['artist']} **{stats['unique_artists']}** artistes différents
{self.theme['emojis']['headphones']} **{total_hours:.1f}h** d'écoute
        """
        embed.add_field(name=f"{self.theme['emojis']['stats']} Statistiques", value=stats_text, inline=False)
        
        # Top titres
        if top_tracks:
            top_tracks_text = ""
            for i, track in enumerate(top_tracks[:5], 1):
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                top_tracks_text += f"{medal} **{track['track_name']}** - {track['artist_name']} ({track['play_count']} écoutes)\n"
            
            embed.add_field(
                name=f"{self.theme['emojis']['fire']} Top Titres",
                value=top_tracks_text,
                inline=False
            )
        
        # Top artistes
        if top_artists:
            top_artists_text = ""
            for i, artist in enumerate(top_artists[:5], 1):
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                hours = (artist['total_time_ms'] / 1000 / 60 / 60)
                top_artists_text += f"{medal} **{artist['artist_name']}** ({artist['play_count']} écoutes • {hours:.1f}h)\n"
            
            embed.add_field(
                name=f"{self.theme['emojis']['artist']} Top Artistes",
                value=top_artists_text,
                inline=False
            )
        
        if top_tracks and top_tracks[0].get('image_url'):
            embed.set_thumbnail(url=top_tracks[0]['image_url'])
        
        embed.set_footer(text="Continue comme ça ! 🎶")
        
        return embed
    
    def new_release(self, release_data, artist_name):
        """Embed pour une nouvelle sortie"""
        release_type_emoji = self.theme['emojis']['album'] if release_data['release_type'] == 'album' else self.theme['emojis']['music']
        release_type_text = "Album" if release_data['release_type'] == 'album' else "Single"
        
        embed = discord.Embed(
            title=f"{self.theme['emojis']['new']} Nouvelle sortie !",
            description=f"**{artist_name}** vient de sortir un nouveau {release_type_text.lower()} !",
            color=self.theme['color'],
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name=f"{release_type_emoji} Titre",
            value=f"**[{release_data['release_name']}]({release_data['spotify_url']})**",
            inline=False
        )
        
        embed.add_field(
            name=f"{self.theme['emojis']['calendar']} Date de sortie",
            value=release_data['release_date'],
            inline=True
        )
        
        if release_data['image_url']:
            embed.set_image(url=release_data['image_url'])
        
        embed.set_footer(text="Écoute-le maintenant sur Spotify !")
        
        return embed
    
    def milestone(self, milestone_type, value, stats):
        """Embed pour un palier atteint"""
        embed = discord.Embed(
            title=f"{self.theme['emojis']['trophy']} Palier atteint !",
            color=0xFFD700,  # Or
            timestamp=datetime.now()
        )
        
        if milestone_type == 'listening_time':
            embed.description = f"Félicitations ! Tu as atteint **{value}h** d'écoute ! {self.theme['emojis']['fire']}"
            embed.add_field(
                name="Temps total",
                value=f"{value}h passées à écouter de la musique",
                inline=False
            )
        
        elif milestone_type == 'tracks_count':
            embed.description = f"Wow ! Tu as écouté **{value} titres** ! {self.theme['emojis']['music']}"
            embed.add_field(
                name="Nombre total",
                value=f"{value} titres écoutés depuis le début",
                inline=False
            )
        
        elif milestone_type == 'artists_count':
            embed.description = f"Incroyable ! Tu as découvert **{value} artistes** ! {self.theme['emojis']['artist']}"
            embed.add_field(
                name="Diversité",
                value=f"{value} artistes différents explorés",
                inline=False
            )
        
        embed.set_footer(text="Continue sur ta lancée ! 🎶")
        
        return embed
    
    def track_info(self, track_info, db_stats):
        """Embed pour les infos d'un titre"""
        embed = discord.Embed(
            title=f"{self.theme['emojis']['music']} {track_info['track_name']}",
            description=f"Par **{track_info['artist_name']}**",
            color=self.theme['color'],
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name=f"{self.theme['emojis']['album']} Album",
            value=track_info['album_name'],
            inline=True
        )
        
        embed.add_field(
            name="⏱️ Durée",
            value=self._format_duration(track_info['duration_ms']),
            inline=True
        )
        
        if db_stats:
            embed.add_field(
                name=f"{self.theme['emojis']['headphones']} Tes écoutes",
                value=f"{db_stats['play_count']} fois",
                inline=True
            )
            
            if db_stats.get('first_listen'):
                embed.add_field(
                    name=f"{self.theme['emojis']['calendar']} Première écoute",
                    value=db_stats['first_listen'].strftime('%d/%m/%Y'),
                    inline=True
                )
        
        embed.add_field(
            name="🔗 Lien",
            value=f"[Écouter sur Spotify]({track_info['spotify_url']})",
            inline=False
        )
        
        if track_info['image_url']:
            embed.set_thumbnail(url=track_info['image_url'])
        
        embed.set_footer(text="Spotify Tracker")
        
        return embed
    
    def artist_info(self, artist_info, db_stats):
        """Embed pour les infos d'un artiste"""
        embed = discord.Embed(
            title=f"{self.theme['emojis']['artist']} {artist_info['artist_name']}",
            color=self.theme['color'],
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name="🎭 Genres",
            value=artist_info['genres'],
            inline=True
        )
        
        embed.add_field(
            name="⭐ Popularité",
            value=f"{artist_info['popularity']}/100",
            inline=True
        )
        
        embed.add_field(
            name="👥 Followers",
            value=f"{artist_info['followers']:,}",
            inline=True
        )
        
        if db_stats:
            total_hours = (db_stats['total_time_ms'] / 1000 / 60 / 60)
            
            embed.add_field(
                name=f"{self.theme['emojis']['headphones']} Tes écoutes",
                value=f"{db_stats['play_count']} titres",
                inline=True
            )
            
            embed.add_field(
                name="⏱️ Temps total",
                value=f"{total_hours:.1f}h",
                inline=True
            )
        
        embed.add_field(
            name="🔗 Lien",
            value=f"[Voir sur Spotify]({artist_info['spotify_url']})",
            inline=False
        )
        
        if artist_info['image_url']:
            embed.set_image(url=artist_info['image_url'])
        
        embed.set_footer(text="Spotify Tracker")
        
        return embed