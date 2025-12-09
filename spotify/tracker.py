"""
Module de suivi de l'activité Spotify
"""

from datetime import datetime
import config

class SpotifyTracker:
    """Classe pour suivre l'activité d'écoute sur Spotify"""
    
    def __init__(self, spotify_client, db_manager):
        self.spotify = spotify_client
        self.db = db_manager
        self.current_track_id = None
        self.last_check_time = None
        self.listening_session_start = None
    
    def is_new_track(self, track_id):
        """Vérifie si c'est un nouveau titre"""
        return track_id != self.current_track_id
    
    def update_current_track(self, track_data):
        """Met à jour le titre actuel"""
        if track_data:
            self.current_track_id = track_data.get('track_id')
            self.last_check_time = datetime.now(config.TIMEZONE)
            
            # Démarrer une nouvelle session d'écoute
            if not self.listening_session_start:
                self.listening_session_start = datetime.now(config.TIMEZONE)
        else:
            self.current_track_id = None
            self.listening_session_start = None
    
    def get_session_duration(self):
        """Retourne la durée de la session d'écoute actuelle"""
        if self.listening_session_start:
            duration = datetime.now(config.TIMEZONE) - self.listening_session_start
            return duration.total_seconds() / 3600  # en heures
        return 0
    
    def reset_session(self):
        """Réinitialise la session d'écoute"""
        self.listening_session_start = None
        self.current_track_id = None
    
    async def process_track_change(self, track_data):
        """Traite un changement de titre"""
        if not track_data:
            self.reset_session()
            return None
        
        track_id = track_data.get('track_id')
        
        if self.is_new_track(track_id):
            # Nouveau titre détecté
            self.update_current_track(track_data)
            
            # Enregistrer dans la base de données
            listening_data = {
                'track_id': track_data['track_id'],
                'track_name': track_data['track_name'],
                'artist_name': track_data['artist_name'],
                'album_name': track_data['album_name'],
                'duration_ms': track_data['duration_ms'],
                'played_at': datetime.now(config.TIMEZONE),
                'image_url': track_data.get('image_url')
            }
            
            self.db.save_track(listening_data)
            
            return {
                'is_new': True,
                'track_data': track_data,
                'play_count': self.db.get_track_play_count(track_id)
            }
        
        return {
            'is_new': False,
            'track_data': track_data
        }
    
    def get_listening_stats(self, period='all'):
        """Récupère les statistiques d'écoute"""
        return self.db.get_stats(period)
    
    def get_track_history(self, track_id):
        """Récupère l'historique d'un titre spécifique"""
        conn = self.db.get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT 
                COUNT(*) as play_count,
                MIN(played_at) as first_listen,
                MAX(played_at) as last_listen,
                SUM(duration_ms) as total_time_ms
            FROM listening_history
            WHERE track_id = %s
        """, (track_id,))
        
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return result
    
    def get_artist_history(self, artist_name):
        """Récupère l'historique d'un artiste"""
        conn = self.db.get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT 
                COUNT(*) as play_count,
                COUNT(DISTINCT track_id) as unique_tracks,
                MIN(played_at) as first_listen,
                MAX(played_at) as last_listen,
                SUM(duration_ms) as total_time_ms
            FROM listening_history
            WHERE artist_name LIKE %s
        """, (f"%{artist_name}%",))
        
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return result
    
    def get_recent_tracks(self, limit=10):
        """Récupère les derniers titres écoutés"""
        conn = self.db.get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT 
                track_name,
                artist_name,
                album_name,
                played_at,
                image_url
            FROM listening_history
            ORDER BY played_at DESC
            LIMIT %s
        """, (limit,))
        
        tracks = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return tracks
    
    def get_discovery_stats(self, period='week'):
        """Récupère les statistiques de découverte"""
        conn = self.db.get_connection()
        cursor = conn.cursor(dictionary=True)
        
        where_clause = ""
        if period == 'week':
            where_clause = "WHERE played_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)"
        elif period == 'month':
            where_clause = "WHERE played_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)"
        elif period == 'year':
            where_clause = "WHERE played_at >= DATE_SUB(NOW(), INTERVAL 365 DAY)"
        
        # Nouveaux titres découverts
        cursor.execute(f"""
            SELECT COUNT(DISTINCT track_id) as new_tracks
            FROM listening_history
            {where_clause}
            AND track_id NOT IN (
                SELECT DISTINCT track_id 
                FROM listening_history 
                WHERE played_at < (
                    SELECT MIN(played_at) 
                    FROM listening_history 
                    {where_clause}
                )
            )
        """)
        
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return result
    
    def check_for_milestones(self):
        """Vérifie si de nouveaux paliers ont été atteints"""
        stats = self.get_listening_stats('all')
        milestones_reached = []
        
        # Temps d'écoute
        total_hours = int(stats['total_time_ms'] / 1000 / 60 / 60) if stats['total_time_ms'] else 0
        for milestone in config.MILESTONES['listening_time']:
            if total_hours >= milestone:
                if self.db.save_milestone('listening_time', milestone):
                    milestones_reached.append({
                        'type': 'listening_time',
                        'value': milestone
                    })
        
        # Nombre de titres
        total_tracks = stats['total_tracks'] or 0
        for milestone in config.MILESTONES['tracks_count']:
            if total_tracks >= milestone:
                if self.db.save_milestone('tracks_count', milestone):
                    milestones_reached.append({
                        'type': 'tracks_count',
                        'value': milestone
                    })
        
        # Nombre d'artistes
        unique_artists = stats['unique_artists'] or 0
        for milestone in config.MILESTONES['artists_count']:
            if unique_artists >= milestone:
                if self.db.save_milestone('artists_count', milestone):
                    milestones_reached.append({
                        'type': 'artists_count',
                        'value': milestone
                    })
        
        return milestones_reached