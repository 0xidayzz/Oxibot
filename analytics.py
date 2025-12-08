import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import io
import discord
from collections import Counter, defaultdict

class BotAnalytics:
    """Module d'analyse et visualisation avancées"""
    
    def __init__(self, db):
        self.db = db
        plt.style.use('dark_background')  # Style Discord-friendly
        
    def generate_listening_trend(self, days=30):
        """Génère un graphique d'évolution des écoutes"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        date_limit = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        cursor.execute('''
            SELECT DATE(played_at) as day, COUNT(*) as count
            FROM spotify_plays
            WHERE played_at >= ?
            GROUP BY DATE(played_at)
            ORDER BY day
        ''', (date_limit,))
        
        data = cursor.fetchall()
        conn.close()
        
        if not data:
            return None
        
        # Prépare les données
        dates = [datetime.strptime(d[0], '%Y-%m-%d') for d in data]
        counts = [d[1] for d in data]
        
        # Crée le graphique
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(dates, counts, marker='o', linewidth=2, markersize=6, 
                color='#1DB954', label='Écoutes')
        
        # Style
        ax.set_xlabel('Date', fontsize=12, color='white')
        ax.set_ylabel('Nombre d\'écoutes', fontsize=12, color='white')
        ax.set_title(f'Évolution des écoutes ({days} derniers jours)', 
                    fontsize=14, color='white', pad=20)
        ax.grid(True, alpha=0.3, linestyle='--')
        ax.legend(loc='upper left')
        
        # Format des dates
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, days//10)))
        plt.xticks(rotation=45)
        
        # Statistiques
        avg = sum(counts) / len(counts)
        ax.axhline(y=avg, color='orange', linestyle='--', 
                  alpha=0.7, label=f'Moyenne: {avg:.1f}')
        
        plt.tight_layout()
        
        # Sauvegarde en mémoire
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, facecolor='#2C2F33')
        buf.seek(0)
        plt.close()
        
        return buf
    
    def generate_activity_heatmap(self):
        """Génère une heatmap d'activité (heures/jours)"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                CAST(strftime('%w', played_at) AS INTEGER) as day_of_week,
                CAST(strftime('%H', played_at) AS INTEGER) as hour,
                COUNT(*) as count
            FROM spotify_plays
            GROUP BY day_of_week, hour
        ''')
        
        data = cursor.fetchall()
        conn.close()
        
        if not data:
            return None
        
        # Matrice 7x24 (jours x heures)
        matrix = [[0 for _ in range(24)] for _ in range(7)]
        for day, hour, count in data:
            matrix[day][hour] = count
        
        # Crée le heatmap
        fig, ax = plt.subplots(figsize=(14, 6))
        im = ax.imshow(matrix, cmap='YlGn', aspect='auto')
        
        # Labels
        days = ['Dim', 'Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam']
        ax.set_yticks(range(7))
        ax.set_yticklabels(days, color='white')
        ax.set_xticks(range(24))
        ax.set_xticklabels(range(24), color='white')
        
        ax.set_xlabel('Heure de la journée', fontsize=12, color='white')
        ax.set_ylabel('Jour de la semaine', fontsize=12, color='white')
        ax.set_title('Heatmap d\'activité musicale', 
                    fontsize=14, color='white', pad=20)
        
        # Colorbar
        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label('Nombre d\'écoutes', color='white')
        cbar.ax.yaxis.set_tick_params(color='white')
        plt.setp(plt.getp(cbar.ax.axes, 'yticklabels'), color='white')
        
        plt.tight_layout()
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, facecolor='#2C2F33')
        buf.seek(0)
        plt.close()
        
        return buf
    
    def generate_genre_distribution(self, limit=8):
        """Génère un camembert des genres (nécessite audio features)"""
        # Note: Nécessite d'enrichir la DB avec les genres via l'API Spotify
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        # Exemple si vous avez une colonne 'genre'
        cursor.execute('''
            SELECT genre, COUNT(*) as count
            FROM spotify_plays
            WHERE genre IS NOT NULL AND genre != ''
            GROUP BY genre
            ORDER BY count DESC
            LIMIT ?
        ''', (limit,))
        
        data = cursor.fetchall()
        conn.close()
        
        if not data:
            return None
        
        labels = [d[0] for d in data]
        sizes = [d[1] for d in data]
        
        # Crée le pie chart
        fig, ax = plt.subplots(figsize=(10, 8))
        colors = plt.cm.Set3(range(len(labels)))
        
        wedges, texts, autotexts = ax.pie(
            sizes, labels=labels, autopct='%1.1f%%',
            startangle=90, colors=colors,
            textprops={'color': 'white', 'fontsize': 11}
        )
        
        for autotext in autotexts:
            autotext.set_color('black')
            autotext.set_fontweight('bold')
        
        ax.set_title('Distribution des genres musicaux', 
                    fontsize=14, color='white', pad=20)
        
        plt.tight_layout()
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, facecolor='#2C2F33')
        buf.seek(0)
        plt.close()
        
        return buf
    
    def analyze_listening_patterns(self):
        """Analyse les patterns d'écoute"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        # Patterns par période de la journée
        cursor.execute('''
            SELECT 
                CASE 
                    WHEN CAST(strftime('%H', played_at) AS INTEGER) BETWEEN 6 AND 11 THEN 'Matin'
                    WHEN CAST(strftime('%H', played_at) AS INTEGER) BETWEEN 12 AND 17 THEN 'Après-midi'
                    WHEN CAST(strftime('%H', played_at) AS INTEGER) BETWEEN 18 AND 22 THEN 'Soirée'
                    ELSE 'Nuit'
                END as period,
                artist_name,
                COUNT(*) as count
            FROM spotify_plays
            WHERE played_at >= date('now', '-30 days')
            GROUP BY period, artist_name
        ''')
        
        data = cursor.fetchall()
        conn.close()
        
        # Organise par période
        patterns = defaultdict(Counter)
        for period, artist, count in data:
            patterns[period][artist] += count
        
        # Trouve le top artiste par période
        results = {}
        for period, artists in patterns.items():
            if artists:
                top_artist, count = artists.most_common(1)[0]
                results[period] = (top_artist, count)
        
        return results
    
    def calculate_streaks(self):
        """Calcule les streaks d'écoute"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT DISTINCT DATE(played_at) as day
            FROM spotify_plays
            ORDER BY day DESC
        ''')
        
        dates = [datetime.strptime(d[0], '%Y-%m-%d').date() for d in cursor.fetchall()]
        conn.close()
        
        if not dates:
            return 0, 0
        
        # Streak actuel
        current_streak = 0
        today = datetime.now().date()
        
        if dates and dates[0] == today:
            current_streak = 1
            for i in range(1, len(dates)):
                if (dates[i-1] - dates[i]).days == 1:
                    current_streak += 1
                else:
                    break
        elif dates and dates[0] == today - timedelta(days=1):
            # Si on a écouté hier
            current_streak = 1
            for i in range(1, len(dates)):
                if (dates[i-1] - dates[i]).days == 1:
                    current_streak += 1
                else:
                    break
        
        # Meilleur streak
        best_streak = 1
        temp_streak = 1
        
        for i in range(1, len(dates)):
            if (dates[i-1] - dates[i]).days == 1:
                temp_streak += 1
                best_streak = max(best_streak, temp_streak)
            else:
                temp_streak = 1
        
        return current_streak, best_streak
    
    def get_mood_analysis(self):
        """Analyse le mood moyen (nécessite audio features de Spotify)"""
        # Cette fonction nécessite d'enrichir la DB avec les audio features
        # valence (0-1), energy (0-1), danceability (0-1)
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT AVG(valence), AVG(energy), AVG(danceability)
            FROM spotify_plays
            WHERE valence IS NOT NULL
            AND played_at >= date('now', '-7 days')
        ''')
        
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0]:
            valence, energy, danceability = result
            
            # Interprétation
            if valence > 0.6 and energy > 0.6:
                mood = "Énergique et joyeux 🎉"
            elif valence > 0.6 and energy < 0.4:
                mood = "Calme et positif 😌"
            elif valence < 0.4 and energy > 0.6:
                mood = "Intense et sombre 🔥"
            else:
                mood = "Mélancolique et doux 🌙"
            
            return {
                'mood': mood,
                'valence': valence,
                'energy': energy,
                'danceability': danceability
            }
        
        return None

# ========== NOUVELLES COMMANDES ==========

@commands.command(name='trend')
async def trend(ctx, days: int = 30):
    """Affiche le graphique d'évolution des écoutes
    Usage: !trend [jours]
    """
    await ctx.send(f"📊 Génération du graphique ({days} jours)...")
    
    analytics = BotAnalytics(ctx.bot.db)
    graph = analytics.generate_listening_trend(days)
    
    if not graph:
        await ctx.send("❌ Pas assez de données pour générer le graphique")
        return
    
    file = discord.File(graph, filename="trend.png")
    embed = discord.Embed(
        title=f"📈 Évolution des écoutes ({days} jours)",
        color=discord.Color.green(),
        timestamp=datetime.now()
    )
    embed.set_image(url="attachment://trend.png")
    
    await ctx.send(embed=embed, file=file)

@commands.command(name='heatmap')
async def heatmap(ctx):
    """Affiche la heatmap d'activité musicale"""
    await ctx.send("🔥 Génération de la heatmap...")
    
    analytics = BotAnalytics(ctx.bot.db)
    graph = analytics.generate_activity_heatmap()
    
    if not graph:
        await ctx.send("❌ Pas assez de données")
        return
    
    file = discord.File(graph, filename="heatmap.png")
    embed = discord.Embed(
        title="🔥 Heatmap d'activité",
        description="Vos heures et jours d'écoute préférés",
        color=discord.Color.orange(),
        timestamp=datetime.now()
    )
    embed.set_image(url="attachment://heatmap.png")
    
    await ctx.send(embed=embed, file=file)

@commands.command(name='patterns')
async def patterns(ctx):
    """Analyse vos patterns d'écoute"""
    await ctx.send("🔍 Analyse de vos habitudes...")
    
    analytics = BotAnalytics(ctx.bot.db)
    patterns = analytics.analyze_listening_patterns()
    
    embed = discord.Embed(
        title="🎯 Vos Patterns d'Écoute",
        description="Artistes préférés par moment de la journée",
        color=discord.Color.purple(),
        timestamp=datetime.now()
    )
    
    period_emojis = {
        'Matin': '🌅',
        'Après-midi': '☀️',
        'Soirée': '🌆',
        'Nuit': '🌙'
    }
    
    for period in ['Matin', 'Après-midi', 'Soirée', 'Nuit']:
        if period in patterns:
            artist, count = patterns[period]
            emoji = period_emojis[period]
            embed.add_field(
                name=f"{emoji} {period}",
                value=f"**{artist}**\n{count} écoutes",
                inline=True
            )
    
    await ctx.send(embed=embed)

@commands.command(name='streak')
async def streak(ctx):
    """Affiche vos streaks d'écoute"""
    analytics = BotAnalytics(ctx.bot.db)
    current, best = analytics.calculate_streaks()
    
    embed = discord.Embed(
        title="🔥 Vos Streaks d'Écoute",
        color=discord.Color.gold(),
        timestamp=datetime.now()
    )
    
    embed.add_field(
        name="⚡ Streak Actuel",
        value=f"**{current} jours** consécutifs",
        inline=True
    )
    
    embed.add_field(
        name="🏆 Meilleur Streak",
        value=f"**{best} jours** consécutifs",
        inline=True
    )
    
    if current >= 7:
        embed.set_footer(text="🎉 Incroyable ! Continuez comme ça !")
    elif current >= 3:
        embed.set_footer(text="👍 Vous êtes régulier !")
    
    await ctx.send(embed=embed)

@commands.command(name='wrapped')
async def wrapped(ctx, periode: str = 'mois'):
    """Récap style Spotify Wrapped
    Usage: !wrapped [mois/année]
    """
    await ctx.send(f"🎁 Génération de votre Wrapped {periode}...")
    
    db = ctx.bot.db
    analytics = BotAnalytics(db)
    
    # Détermine la période
    if periode.lower() in ['mois', 'month']:
        days = 30
        title = "🎁 Votre Wrapped du Mois"
    else:
        days = 365
        title = "🎁 Votre Wrapped de l'Année"
    
    # Stats globales
    total_plays = db.get_track_play_count()
    total_time = db.get_total_listening_time()
    top_tracks = db.get_top_tracks(3)
    top_artists = db.get_top_artists(3)
    current, best = analytics.calculate_streaks()
    
    embed = discord.Embed(
        title=title,
        description=f"Vos stats des {days} derniers jours",
        color=discord.Color.purple(),
        timestamp=datetime.now()
    )
    
    # Temps d'écoute
    hours = total_time // 60
    embed.add_field(
        name="⏱️ Temps d'Écoute",
        value=f"**{hours}h {total_time % 60}m**\n{total_plays} titres écoutés",
        inline=False
    )
    
    # Top Track
    if top_tracks:
        track = top_tracks[0]
        embed.add_field(
            name="🎵 Votre Top #1",
            value=f"**{track[0]}**\n*{track[1]}*\n{track[2]} écoutes",
            inline=False
        )
    
    # Top Artiste
    if top_artists:
        artist = top_artists[0]
        embed.add_field(
            name="🎤 Artiste Préféré",
            value=f"**{artist[0]}**\n{artist[1]} écoutes",
            inline=False
        )
    
    # Streak
    embed.add_field(
        name="🔥 Meilleur Streak",
        value=f"{best} jours consécutifs",
        inline=True
    )
    
    embed.set_footer(text="🎉 Merci d'avoir écouté avec nous !")
    
    await ctx.send(embed=embed)
    
    # Génère le graphique
    graph = analytics.generate_listening_trend(days)
    if graph:
        file = discord.File(graph, filename="wrapped.png")
        await ctx.send(file=file)