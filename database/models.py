"""
Modèles de données pour la base de données
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class Track:
    """Modèle pour un titre"""
    track_id: str
    track_name: str
    artist_name: str
    album_name: str
    duration_ms: int
    image_url: Optional[str] = None
    spotify_url: Optional[str] = None
    
    def to_dict(self):
        return {
            'track_id': self.track_id,
            'track_name': self.track_name,
            'artist_name': self.artist_name,
            'album_name': self.album_name,
            'duration_ms': self.duration_ms,
            'image_url': self.image_url,
            'spotify_url': self.spotify_url
        }

@dataclass
class ListeningHistory:
    """Modèle pour l'historique d'écoute"""
    id: Optional[int] = None
    track_id: str = ""
    track_name: str = ""
    artist_name: str = ""
    album_name: str = ""
    duration_ms: int = 0
    played_at: Optional[datetime] = None
    image_url: Optional[str] = None
    
    def to_dict(self):
        return {
            'id': self.id,
            'track_id': self.track_id,
            'track_name': self.track_name,
            'artist_name': self.artist_name,
            'album_name': self.album_name,
            'duration_ms': self.duration_ms,
            'played_at': self.played_at,
            'image_url': self.image_url
        }

@dataclass
class Artist:
    """Modèle pour un artiste"""
    artist_id: str
    artist_name: str
    genres: Optional[str] = None
    popularity: Optional[int] = None
    followers: Optional[int] = None
    image_url: Optional[str] = None
    spotify_url: Optional[str] = None
    
    def to_dict(self):
        return {
            'artist_id': self.artist_id,
            'artist_name': self.artist_name,
            'genres': self.genres,
            'popularity': self.popularity,
            'followers': self.followers,
            'image_url': self.image_url,
            'spotify_url': self.spotify_url
        }

@dataclass
class Release:
    """Modèle pour une sortie (album/single)"""
    release_id: str
    artist_id: str
    release_name: str
    release_type: str  # 'album' ou 'single'
    release_date: str
    image_url: Optional[str] = None
    spotify_url: Optional[str] = None
    
    def to_dict(self):
        return {
            'release_id': self.release_id,
            'artist_id': self.artist_id,
            'release_name': self.release_name,
            'release_type': self.release_type,
            'release_date': self.release_date,
            'image_url': self.image_url,
            'spotify_url': self.spotify_url
        }

@dataclass
class GuildConfig:
    """Modèle pour la configuration d'un serveur Discord"""
    guild_id: int
    spotify_channel_id: Optional[int] = None
    news_channel_id: Optional[int] = None
    main_channel_id: Optional[int] = None
    theme_color: int = 0x9B59B6
    
    def to_dict(self):
        return {
            'guild_id': self.guild_id,
            'spotify_channel_id': self.spotify_channel_id,
            'news_channel_id': self.news_channel_id,
            'main_channel_id': self.main_channel_id,
            'theme_color': self.theme_color
        }

@dataclass
class Milestone:
    """Modèle pour un palier atteint"""
    milestone_type: str  # 'listening_time', 'tracks_count', 'artists_count'
    milestone_value: int
    achieved_at: Optional[datetime] = None
    
    def to_dict(self):
        return {
            'milestone_type': self.milestone_type,
            'milestone_value': self.milestone_value,
            'achieved_at': self.achieved_at
        }

@dataclass
class Stats:
    """Modèle pour les statistiques"""
    total_tracks: int = 0
    total_time_ms: int = 0
    unique_tracks: int = 0
    unique_artists: int = 0
    
    def to_dict(self):
        return {
            'total_tracks': self.total_tracks,
            'total_time_ms': self.total_time_ms,
            'unique_tracks': self.unique_tracks,
            'unique_artists': self.unique_artists
        }
    
    @property
    def total_hours(self):
        """Retourne le temps total en heures"""
        return self.total_time_ms / 1000 / 60 / 60 if self.total_time_ms else 0