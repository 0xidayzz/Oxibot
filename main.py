# main.py
import discord
from discord.ext import commands
import os
import sys

# Import des helpers et cogs
from keep_alive import keep_alive
from helpers.database import setup_database, get_stats_for_presence
from cogs.music_tracker_cog import MusicTracker
from cogs.admin_cog import Admin
from cogs.stats_cog import Stats # Import des squelettes

# --- Vérification des Tokens (Le point critique) ---

REQUIRED_SECRETS = [
    'DISCORD_TOKEN', 
    'SPOTIFY_CLIENT_ID', 
    'SPOTIFY_CLIENT_SECRET', 
    'SPOTIFY_REFRESH_TOKEN',
    'SPOTIFY_USER_ID'
]

missing_secrets = [secret for secret in REQUIRED_SECRETS if not os.getenv(secret)]

if missing_secrets:
    print("=========================================================")
    print("🚨 ERREUR CRITIQUE : SECRETS MANQUANTS 🚨")
    print("Le bot ne peut pas démarrer sans les variables d'environnement suivantes.")
    print("Veuillez cliquer sur l'icône 'Cadenas' (Secrets) à gauche de Replit et les ajouter :")
    print("-" * 50)
    for secret in missing_secrets:
        print(f"👉 CLÉ MANQUANTE : {secret}")
    print("-" * 50)
    print("👉 NOTE IMPORTANTE : SPOTIFY_REFRESH_TOKEN doit être obtenu via l'OAuth Spotify.")
    print("=========================================================")
    # Quitter proprement pour forcer l'utilisateur à régler le problème
    sys.exit(1) 


# --- Initialisation ---

setup_database()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True 
intents.presences = True # Utile pour certains événements

bot = commands.Bot(command_prefix='/', intents=intents, help_command=None)

# 3. Charger les Cogs
bot.add_cog(MusicTracker(bot))
bot.add_cog(Admin(bot))
bot.add_cog(Stats(bot))


# --- Commandes de Base et Événements ---

@bot.event
async def on_ready():
    print('----------------------------------')
    print(f'Bot démarré. Nom: {bot.user}')
    print(f'Prêt sur {len(bot.guilds)} serveurs.')
    print('----------------------------------')
    
    # Mise à jour du statut avec les statistiques
    stats = get_stats_for_presence()
    
    status_message = (
        f"🎧 {stats['total_hours']:.1f}h | "
        f"⭐ {stats['top_artist']} | "
        f"🎵 {stats['last_track']}"
    )

    await bot.change_presence(activity=discord.CustomActivity(name=status_message))
    
@bot.command(name='help')
async def help_command(ctx):
    """Affiche la liste des commandes."""
    embed = discord.Embed(
        title="🤖 Aide du Bot Spotify Tracker",
        description="Prefixe des commandes : `/`",
        color=0x9B59B6
    )
    embed.add_field(name="🎶 Suivi Musique", value="`/song`, `/setchannel musique`", inline=False)
    embed.add_field(name="📊 Statistiques (WIP)", value="`/stats (all, week, etc.)`, `/wrapped`, `/graph`, `/search`, `/new`, `/recap`", inline=False)
    embed.add_field(name="⭐ Artistes Suivis (WIP)", value="`/follow`, `/listfollow`, `/unfollow`, `/setchannel follow`", inline=False)
    embed.add_field(name="⚙️ Administration", value="`/setchannel (musique|annonce|wrapped|follow)`, `/theme`", inline=False)
    
    await ctx.send(embed=embed)


# --- Démarrage ---

if __name__ == '__main__':
    # Lance le serveur web pour garder le bot actif sur Replit
    keep_alive() 
    
    TOKEN = os.getenv('DISCORD_TOKEN')
    try:
        bot.run(TOKEN)
    except discord.errors.LoginFailure:
        print("\n❌ ERREUR: Le DISCORD_TOKEN est invalide. Veuillez vérifier le secret.")
    except Exception as e:
        print(f"\n❌ ERREUR INCONNUE AU DÉMARRAGE: {e}")