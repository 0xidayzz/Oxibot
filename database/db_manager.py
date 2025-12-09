import mysql.connector
from mysql.connector import pooling
from datetime import datetime
import config

class DatabaseManager:
    def __init__(self):
        self.pool = pooling.MySQLConnectionPool(
            pool_name="spotify_pool",
            pool_size=5,
            **config.MYSQL_CONFIG
        )
        self.init_database()
    
    def get_connection(self):
        return self.pool.get_connection()
    
    def init_database(self):
        """Crée les tables si elles n'existent pas"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Table des configurations
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS config (
                id INT PRIMARY KEY AUTO_INCREMENT,
                guild_id BIGINT UNIQUE,
                spotify_channel_id BIGINT,
                news_channel_id BIGINT,
                main_channel_id BIGINT,
                theme_color INT DEFAULT 10181046,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Table des écoutes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS listening_history (
                id INT PRIMARY KEY AUTO_INCREMENT,
                track_id VARCHAR(255),
                track_name VARCHAR(500),
                artist_name VARCHAR(500),
                album_name VARCHAR(500),
                duration_ms INT,
                played_at TIMESTAMP,
                image_url VARCHAR(1000),
                INDEX idx_track_id (track_id),
                INDEX idx_played_at (played_at)
            )
        """)
        
        # Table des artistes suivis
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS followed_artists (
                id INT PRIMARY KEY AUTO_INCREMENT,
                artist_id VARCHAR(255) UNIQUE,
                artist_name VARCHAR(500),
                last_checked TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Table des nouvelles sorties
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS new_releases (
                id INT PRIMARY KEY AUTO_INCREMENT,
                release_id VARCHAR(255) UNIQUE,
                artist_id VARCHAR(255),
                release_name VARCHAR(500),
                release_type VARCHAR(50),
                release_date DATE,
                image_url VARCHAR(1000),
                notified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_artist_id (artist_id)
            )
        """)
        
        # Table des paliers atteints
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS milestones_achieved (
                id INT PRIMARY KEY AUTO_INCREMENT,
                milestone_type VARCHAR(50),
                milestone_value INT,
                achieved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY unique_milestone (milestone_type, milestone_value)
            )
        """)
        
        conn.commit()
        cursor.close()
        conn.close()
    
    def save_track(self, track_data):
        """Enregistre une écoute"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO listening_history 
            (track_id, track_name, artist_name, album_name, duration_ms, played_at, image_url)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            track_data['track_id'],
            track_data['track_name'],
            track_data['artist_name'],
            track_data['album_name'],
            track_data['duration_ms'],
            track_data['played_at'],
            track_data['image_url']
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
    
    def get_track_play_count(self, track_id):
        """Récupère le nombre d'écoutes d'un titre"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) FROM listening_history WHERE track_id = %s
        """, (track_id,))
        
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        
        return count
    
    def get_channel_config(self, guild_id):
        """Récupère la configuration des channels"""
        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT * FROM config WHERE guild_id = %s
        """, (guild_id,))
        
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return result
    
    def set_channel(self, guild_id, channel_type, channel_id):
        """Configure un channel"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO config (guild_id, {}_channel_id)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE {}_channel_id = %s
        """.format(channel_type, channel_type), (guild_id, channel_id, channel_id))
        
        conn.commit()
        cursor.close()
        conn.close()
    
    def get_stats(self, period='all'):
        """Récupère les statistiques d'écoute"""
        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)
        
        where_clause = ""
        if period == 'week':
            where_clause = "WHERE played_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)"
        elif period == 'month':
            where_clause = "WHERE played_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)"
        elif period == 'year':
            where_clause = "WHERE played_at >= DATE_SUB(NOW(), INTERVAL 365 DAY)"
        
        # Total d'écoutes et temps
        cursor.execute(f"""
            SELECT 
                COUNT(*) as total_tracks,
                SUM(duration_ms) as total_time_ms,
                COUNT(DISTINCT track_id) as unique_tracks,
                COUNT(DISTINCT artist_name) as unique_artists
            FROM listening_history
            {where_clause}
        """)
        
        stats = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return stats
    
    def get_top_tracks(self, limit=10, period='all'):
        """Récupère les titres les plus écoutés"""
        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)
        
        where_clause = ""
        if period == 'week':
            where_clause = "WHERE played_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)"
        elif period == 'month':
            where_clause = "WHERE played_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)"
        elif period == 'year':
            where_clause = "WHERE played_at >= DATE_SUB(NOW(), INTERVAL 365 DAY)"
        
        cursor.execute(f"""
            SELECT 
                track_name,
                artist_name,
                COUNT(*) as play_count,
                image_url
            FROM listening_history
            {where_clause}
            GROUP BY track_id, track_name, artist_name, image_url
            ORDER BY play_count DESC
            LIMIT %s
        """, (limit,))
        
        tracks = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return tracks
    
    def get_top_artists(self, limit=10, period='all'):
        """Récupère les artistes les plus écoutés"""
        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)
        
        where_clause = ""
        if period == 'week':
            where_clause = "WHERE played_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)"
        elif period == 'month':
            where_clause = "WHERE played_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)"
        elif period == 'year':
            where_clause = "WHERE played_at >= DATE_SUB(NOW(), INTERVAL 365 DAY)"
        
        cursor.execute(f"""
            SELECT 
                artist_name,
                COUNT(*) as play_count,
                SUM(duration_ms) as total_time_ms
            FROM listening_history
            {where_clause}
            GROUP BY artist_name
            ORDER BY play_count DESC
            LIMIT %s
        """, (limit,))
        
        artists = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return artists
    
    def save_milestone(self, milestone_type, value):
        """Enregistre un palier atteint"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO milestones_achieved (milestone_type, milestone_value)
                VALUES (%s, %s)
            """, (milestone_type, value))
            conn.commit()
            result = True
        except mysql.connector.IntegrityError:
            result = False
        
        cursor.close()
        conn.close()
        return result