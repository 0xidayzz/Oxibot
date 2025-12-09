"""
Fonctions utilitaires diverses
"""

from datetime import datetime, timedelta
import re
import config

def format_duration(milliseconds):
    """
    Convertit des millisecondes en format lisible
    
    Args:
        milliseconds: Durée en millisecondes
    
    Returns:
        str: Durée formatée (ex: "3h 45m" ou "2m 30s")
    """
    if not milliseconds:
        return "0s"
    
    seconds = milliseconds // 1000
    minutes = seconds // 60
    hours = minutes // 60
    days = hours // 24
    
    if days > 0:
        return f"{days}j {hours % 24}h"
    elif hours > 0:
        return f"{hours}h {minutes % 60}m"
    elif minutes > 0:
        return f"{minutes}m {seconds % 60}s"
    else:
        return f"{seconds}s"

def format_number(number):
    """
    Formate un nombre avec des séparateurs de milliers
    
    Args:
        number: Nombre à formater
    
    Returns:
        str: Nombre formaté (ex: "1 234 567")
    """
    if not number:
        return "0"
    return f"{number:,}".replace(",", " ")

def get_period_dates(period):
    """
    Retourne les dates de début et fin pour une période donnée
    
    Args:
        period: 'week', 'month', 'year', ou 'all'
    
    Returns:
        tuple: (date_debut, date_fin)
    """
    now = datetime.now(config.TIMEZONE)
    
    if period == 'week':
        start_date = now - timedelta(days=7)
    elif period == 'month':
        start_date = now - timedelta(days=30)
    elif period == 'year':
        start_date = now - timedelta(days=365)
    else:  # all
        start_date = None
    
    return start_date, now

def validate_hex_color(color_string):
    """
    Valide et convertit une couleur hexadécimale
    
    Args:
        color_string: Chaîne de couleur (ex: "#9B59B6" ou "9B59B6")
    
    Returns:
        int: Couleur en entier ou None si invalide
    """
    # Enlever le # si présent
    color_string = color_string.strip().replace('#', '')
    
    # Vérifier le format
    if not re.match(r'^[0-9A-Fa-f]{6}$', color_string):
        return None
    
    try:
        return int(color_string, 16)
    except ValueError:
        return None

def truncate_string(text, max_length=50, suffix="..."):
    """
    Tronque une chaîne de caractères si elle dépasse la longueur maximale
    
    Args:
        text: Texte à tronquer
        max_length: Longueur maximale
        suffix: Suffixe à ajouter si tronqué
    
    Returns:
        str: Texte tronqué
    """
    if not text:
        return ""
    
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix

def get_progress_bar(current, total, length=20):
    """
    Génère une barre de progression
    
    Args:
        current: Valeur actuelle
        total: Valeur totale
        length: Longueur de la barre
    
    Returns:
        str: Barre de progression (ex: "████████░░░░░░░░░░░░ 40%")
    """
    if total == 0:
        return "░" * length + " 0%"
    
    percentage = min(100, int((current / total) * 100))
    filled = int((percentage / 100) * length)
    empty = length - filled
    
    bar = "█" * filled + "░" * empty
    return f"{bar} {percentage}%"

def calculate_listening_streak(db_manager):
    """
    Calcule la série d'écoute consécutive en jours
    
    Args:
        db_manager: Instance du gestionnaire de base de données
    
    Returns:
        int: Nombre de jours consécutifs
    """
    conn = db_manager.get_connection()
    cursor = conn.cursor()
    
    # Récupérer les dates avec des écoutes
    cursor.execute("""
        SELECT DISTINCT DATE(played_at) as date
        FROM listening_history
        ORDER BY date DESC
        LIMIT 365
    """)
    
    dates = [row[0] for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    
    if not dates:
        return 0
    
    streak = 1
    current_date = dates[0]
    
    for i in range(1, len(dates)):
        previous_date = dates[i]
        diff = (current_date - previous_date).days
        
        if diff == 1:
            streak += 1
            current_date = previous_date
        else:
            break
    
    return streak

def get_emoji_for_genre(genre):
    """
    Retourne un emoji approprié pour un genre musical
    
    Args:
        genre: Nom du genre
    
    Returns:
        str: Emoji correspondant
    """
    genre_lower = genre.lower()
    
    emoji_map = {
        'rock': '🎸',
        'pop': '🎤',
        'rap': '🎤',
        'hip hop': '🎤',
        'electronic': '🎹',
        'edm': '🎹',
        'jazz': '🎷',
        'classical': '🎻',
        'metal': '🤘',
        'country': '🤠',
        'blues': '🎺',
        'reggae': '🌴',
        'folk': '🪕',
        'indie': '🎸',
        'r&b': '🎤',
        'soul': '🎤'
    }
    
    for key, emoji in emoji_map.items():
        if key in genre_lower:
            return emoji
    
    return '🎵'

def get_time_of_day_emoji():
    """
    Retourne un emoji en fonction de l'heure de la journée
    
    Returns:
        str: Emoji correspondant
    """
    hour = datetime.now(config.TIMEZONE).hour
    
    if 5 <= hour < 12:
        return '🌅'  # Matin
    elif 12 <= hour < 18:
        return '☀️'  # Après-midi
    elif 18 <= hour < 22:
        return '🌆'  # Soirée
    else:
        return '🌙'  # Nuit

def format_listening_time_message(hours):
    """
    Génère un message sympathique basé sur le temps d'écoute
    
    Args:
        hours: Nombre d'heures d'écoute
    
    Returns:
        str: Message personnalisé
    """
    if hours < 1:
        return "Tu débutes ton aventure musicale ! 🎵"
    elif hours < 10:
        return "Bon début ! Continue comme ça ! 🎧"
    elif hours < 50:
        return "Tu es un vrai mélomane ! 🎶"
    elif hours < 100:
        return "Impressionnant ! La musique c'est la vie ! 🔥"
    elif hours < 500:
        return "Tu es accro à la musique ! 🎵✨"
    elif hours < 1000:
        return "Légende de la musique ! 🏆"
    else:
        return "Tu es une ICÔNE musicale ! 👑🎵"

def get_period_label(period):
    """
    Retourne le label français d'une période
    
    Args:
        period: 'week', 'month', 'year', ou 'all'
    
    Returns:
        str: Label en français
    """
    labels = {
        'week': 'Cette semaine',
        'month': 'Ce mois-ci',
        'year': 'Cette année',
        'all': 'Depuis le début'
    }
    return labels.get(period, period)

def create_leaderboard_text(items, name_key='name', value_key='value', max_length=30):
    """
    Crée un texte formaté pour un classement
    
    Args:
        items: Liste d'éléments avec nom et valeur
        name_key: Clé pour le nom
        value_key: Clé pour la valeur
        max_length: Longueur maximale du nom
    
    Returns:
        str: Texte formaté
    """
    if not items:
        return "Aucune donnée disponible"
    
    text = ""
    medals = ["🥇", "🥈", "🥉"]
    
    for i, item in enumerate(items, 1):
        medal = medals[i-1] if i <= 3 else f"{i}."
        name = truncate_string(item[name_key], max_length)
        value = item[value_key]
        
        text += f"{medal} **{name}** - {value}\n"
    
    return text