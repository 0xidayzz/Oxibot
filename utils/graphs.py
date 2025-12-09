import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import io
import mysql.connector
import config

class GraphGenerator:
    def __init__(self, db_manager):
        self.db = db_manager
        plt.style.use('dark_background')
    
    def _get_listening_data_by_period(self, period, data_type='tracks'):
        """Récupère les données d'écoute par période"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        if period == 'week':
            date_format = '%Y-%m-%d'
            days = 7
            group_by = 'DATE(played_at)'
        elif period == 'month':
            date_format = '%Y-%m-%d'
            days = 30
            group_by = 'DATE(played_at)'
        else:  # year
            date_format = '%Y-%m'
            days = 365
            group_by = 'DATE_FORMAT(played_at, "%Y-%m")'
        
        if data_type == 'time':
            cursor.execute(f"""
                SELECT 
                    {group_by} as date,
                    SUM(duration_ms) / 3600000 as hours
                FROM listening_history
                WHERE played_at >= DATE_SUB(NOW(), INTERVAL {days} DAY)
                GROUP BY date
                ORDER BY date
            """)
        elif data_type == 'new_tracks':
            cursor.execute(f"""
                SELECT 
                    {group_by} as date,
                    COUNT(DISTINCT track_id) as count
                FROM listening_history
                WHERE played_at >= DATE_SUB(NOW(), INTERVAL {days} DAY)
                GROUP BY date
                ORDER BY date
            """)
        else:  # tracks count
            cursor.execute(f"""
                SELECT 
                    {group_by} as date,
                    COUNT(*) as count
                FROM listening_history
                WHERE played_at >= DATE_SUB(NOW(), INTERVAL {days} DAY)
                GROUP BY date
                ORDER BY date
            """)
        
        data = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return data
    
    def _get_artist_data(self, period):
        """Récupère les données par artiste"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        days = 7 if period == 'week' else 30 if period == 'month' else 365
        
        cursor.execute(f"""
            SELECT 
                artist_name,
                COUNT(*) as count
            FROM listening_history
            WHERE played_at >= DATE_SUB(NOW(), INTERVAL {days} DAY)
            GROUP BY artist_name
            ORDER BY count DESC
            LIMIT 10
        """)
        
        data = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return data
    
    def generate_graph(self, graph_type, period):
        """Génère un graphique selon le type demandé"""
        fig, ax = plt.subplots(figsize=(12, 6), facecolor='#2C2F33')
        ax.set_facecolor('#23272A')
        
        if graph_type == 'time':
            data = self._get_listening_data_by_period(period, 'time')
            dates = [row[0] for row in data]
            values = [row[1] for row in data]
            
            ax.plot(dates, values, color='#9B59B6', linewidth=2.5, marker='o', markersize=6)
            ax.fill_between(dates, values, alpha=0.3, color='#9B59B6')
            ax.set_ylabel('Heures d\'écoute', color='white', fontsize=12)
            title = f'Temps d\'écoute - {self._get_period_label(period)}'
        
        elif graph_type == 'titre':
            data = self._get_listening_data_by_period(period, 'tracks')
            dates = [row[0] for row in data]
            values = [row[1] for row in data]
            
            ax.bar(dates, values, color='#9B59B6', alpha=0.8, edgecolor='white', linewidth=0.5)
            ax.set_ylabel('Nombre de titres', color='white', fontsize=12)
            title = f'Titres écoutés - {self._get_period_label(period)}'
        
        elif graph_type == 'newTitre':
            data = self._get_listening_data_by_period(period, 'new_tracks')
            dates = [row[0] for row in data]
            values = [row[1] for row in data]
            
            ax.bar(dates, values, color='#E91E63', alpha=0.8, edgecolor='white', linewidth=0.5)
            ax.set_ylabel('Nouveaux titres découverts', color='white', fontsize=12)
            title = f'Découvertes - {self._get_period_label(period)}'
        
        elif graph_type == 'artiste':
            data = self._get_artist_data(period)
            artists = [row[0][:20] + '...' if len(row[0]) > 20 else row[0] for row in data]
            values = [row[1] for row in data]
            
            bars = ax.barh(artists, values, color='#9B59B6', alpha=0.8, edgecolor='white', linewidth=0.5)
            ax.set_xlabel('Nombre d\'écoutes', color='white', fontsize=12)
            title = f'Top Artistes - {self._get_period_label(period)}'
            
            # Inverser l'ordre pour avoir le top en haut
            ax.invert_yaxis()
        
        ax.set_title(title, color='white', fontsize=16, fontweight='bold', pad=20)
        ax.tick_params(colors='white', labelsize=10)
        ax.grid(True, alpha=0.2, linestyle='--', color='white')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['bottom'].set_color('white')
        ax.spines['left'].set_color('white')
        
        # Rotation des labels de date si nécessaire
        if graph_type != 'artiste':
            plt.xticks(rotation=45, ha='right')
        
        plt.tight_layout()
        
        # Sauvegarder dans un buffer
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150, facecolor='#2C2F33')
        buffer.seek(0)
        plt.close()
        
        return buffer
    
    def _get_period_label(self, period):
        """Retourne le label de la période"""
        labels = {
            'week': 'Dernière semaine',
            'month': 'Dernier mois',
            'year': 'Dernière année'
        }
        return labels.get(period, period)